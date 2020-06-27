import argparse
import logging
import random
import rpyc
import threading
import time

from rpyc import Service
from rpyc.utils.server import ThreadPoolServer

logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter(
        '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


FOLLOWER = "follower"
CANDIDATE = "candidate"
LEADER = "leader"


class Peer:
    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port
        self.conn = None


class RaftServer(Service):
    def __init__(self, id, peers):
        # ID, peers
        self.id = id
        self.peers = peers
        self.leader_id = None

        # persistant state
        self.current_term = 0
        self.voted_for = None
        self.log = []
        # Volatile state All
        self.commit_index = 0
        self.last_applied = 0
        # Volatile state Leader
        self.next_index = []
        self.match_index = []
        # Current state
        self.state = FOLLOWER
        self.lock = threading.Lock()
        # Election timer
        self.reset_event = threading.Event()
        self.stop_event = threading.Event()
        self.follower_event = threading.Event()
        self.follower_event.set()
        self.election_timer = threading.Thread(
            target=self.election_timeout,
            args=('election_timeout',),
            daemon=True,
        )
        self.election_timer.start()
        # Candidate stuff
        self.candidate_event = threading.Event()
        self.candidate_timer_reset_event = threading.Event()
        self.candidate_timer_expired_event = threading.Event()
        self.candidate_election_timer = threading.Thread(
            target=self.candidate_election_timeout,
            args=('candidate_election_timeout',),
            daemon=True,
        )
        self.candidate_election_timer.start()
        self.candidate_loop = threading.Thread(
            target=self.candidate_loop,
            args=('candidate_loop',),
            daemon=True,
        )
        self.candidate_loop.start()
        # Leader stuff
        self.leader_event = threading.Event()
        self.leader_loop = threading.Thread(
            target=self.leader_loop,
            args=('leader_loop',),
            daemon=True,
        )
        self.leader_loop.start()

    def switch_state_to(self, state):
        with self.lock:
            current_state = self.state
            current_event = getattr(self, current_state + '_event')
            current_event.clear()
            self.state = state
            new_event = getattr(self, state + '_event')
            new_event.set()

    def election_timeout(self, name):
        """The election timeout loop that runs by followers
        """
        logger.info("Thread %s: starting", name)
        while not self.stop_event.is_set():
            # Must be a follower to run
            if not self.follower_event.is_set():
                logger.info("Thread %s: Not FOLLOWER, will wait now..", name)
            self.follower_event.wait()
            timeout = random.randint(5, 10)
            logger.info(
                "Thread %s: Setting election timeout to %s secs",
                name,
                timeout
            )
            if not self.reset_event.wait(timeout):
                if self.stop_event.is_set():
                    break
                logger.info("Thread %s: Timed out: Starting election", name)
                self.reset_event.clear()
                self.switch_state_to(CANDIDATE)
                continue

            logger.info("Thread %s: Reseting timer", name)
            self.reset_event.clear()
            continue

    def candidate_election_timeout(self, name):
        """The election timeout loop that runs by candidates
        """
        logger.info("Thread %s: starting", name)
        while not self.stop_event.is_set():
            # Must be a candidate to run
            if not self.candidate_event.is_set():
                logger.info("Thread %s: Not CANDIDATE, will wait now..", name)
            self.candidate_event.wait()
            timeout = random.randint(5, 10)
            logger.info(
                "Thread %s: Setting candidate election timeout to %s secs",
                name,
                timeout
            )
            if not self.candidate_timer_reset_event.wait(timeout):
                if self.stop_event.is_set():
                    break
                logger.info("Thread %s: Timed out: Starting new election",
                            name)
                self.candidate_timer_expired_event.set()
                continue

            logger.info("Thread %s: Reseting timer", name)
            self.candidate_timer_reset_event.clear()
            continue

    def candidate_loop(self, name):
        """The candidate loop
        """
        logger.info("Thread %s: starting", name)
        while not self.stop_event.is_set():
            # Must be a candidate to run
            if not self.candidate_event.is_set():
                logger.info("Thread %s: Not CANDIDATE, will wait now..", name)
            self.candidate_event.wait()
            with self.lock:
                self.current_term += 1
                logger.info(
                    "Thread %s: Incremented Current Term to %s",
                    name,
                    self.current_term
                )
            votes = 1
            async_results = {}
            sent_peers_set = set()
            while True:
                if self.candidate_timer_expired_event.is_set():
                    break
                # Setup RPC connections
                for peer_id in self.peers:
                    if not self.peers[peer_id].conn:
                        hostname = self.peers[peer_id].hostname
                        port = self.peers[peer_id].port
                        try:
                            self.peers[peer_id].conn = rpyc.connect(
                                hostname, port,
                                keepalive=True
                            )
                        except ConnectionError:
                            pass
                # Send async RequestVoteRPC
                for peer_id in self.peers:
                    conn = self.peers[peer_id].conn
                    if conn:
                        try:
                            request_vote_async = rpyc.async_(
                                conn.root.request_vote_rpc)
                            if peer_id not in sent_peers_set:
                                async_results[peer_id] = request_vote_async(
                                    self.current_term, self.id)
                                sent_peers_set.add(peer_id)
                        except EOFError:
                            self.peers[peer_id].conn = None
                returned_results = []
                for peer_id, async_result in async_results.items():
                    if async_result.ready:
                        value = async_result.value
                        term, voted_granted = value
                        if voted_granted:
                            votes += 1
                        if term > self.current_term:
                            with self.lock:
                                self.current_term = term
                            self.switch_state_to(FOLLOWER)
                            break
                        returned_results.append(peer_id)
                for peer_id in returned_results:
                    async_results.pop(peer_id)
                # If collected majority become leader
                if votes >= len(self.peers) // 2 + 1:
                    logger.info("Thread %s: Switching to LEADER", name)
                    self.switch_state_to(LEADER)
                    break

            self.candidate_timer_expired_event.clear()

    def leader_loop(self, name):
        """The leader loop
        """
        logger.info("Thread %s: starting", name)
        while not self.stop_event.is_set():
            # Must be a leader to run
            if not self.leader_event.is_set():
                logger.info("Thread %s: Not LEADER, will wait now..", name)
            self.leader_event.wait()
            logger.info("Thread %s: Became LEADER.", name)
            async_results = []
            while True:
                logger.info("Thread %s: Sending Heartbeats...", name)
                # Setup RPC connections
                for peer_id in self.peers:
                    if not self.peers[peer_id].conn:
                        hostname = self.peers[peer_id].hostname
                        port = self.peers[peer_id].port
                        try:
                            self.peers[peer_id].conn = rpyc.connect(
                                hostname, port, keepalive=True)
                        except ConnectionError:
                            pass
                # Send async AppendEntriesRPC as heartbeats
                for peer_id in self.peers:
                    conn = self.peers[peer_id].conn
                    if conn:
                        try:
                            request_vote_async = rpyc.async_(
                                conn.root.append_entries_rpc)
                            async_results.append(request_vote_async(
                                self.current_term, self.id))
                        except EOFError:
                            self.peers[peer_id].conn = None
                returned_results = []
                for async_result in async_results:
                    if async_result.ready:
                        returned_results.append(async_result)
                        value = async_result.value
                        term, success = value
                        if term > self.current_term:
                            with self.lock:
                                self.current_term = term
                            self.switch_state_to(FOLLOWER)
                            break
                async_results = [result for result in async_results
                                 if result not in returned_results]
                time.sleep(2)

    def exposed_request_vote_rpc(self, term, candidate_id):
        """Request Votes RPC
        """
        logger.info("Called the Request Votes RPC")
        logger.info(term)
        logger.info(self.current_term)
        with self.lock:
            if term < self.current_term:
                return self.current_term, False
            else:
                self.voted_for = candidate_id
        if term > self.current_term:
            with self.lock:
                self.current_term = term
            self.switch_state_to(FOLLOWER)
        self.reset_event.set()
        return term, True

    def exposed_append_entries_rpc(self, term, leader_id):
        """Append Entries RPC
        """
        logger.info("Called the Append Entries RPC")
        with self.lock:
            if term < self.current_term:
                return self.current_term, False
            else:
                self.leader_id = leader_id
        self.switch_state_to(FOLLOWER)
        self.reset_event.set()
        self.candidate_timer_reset_event.set()
        return term, True

    def exposed_is_leader(self):
        return False


def parse_raft_config(raft_config_filename):
    nodes = {}
    with open(raft_config_filename, 'r') as f:
        for line in f:
            node_name, params = line.split(':', maxsplit=1)
            if not node_name.startswith('node'):
                raise Exception('Invalid node name')
            node_number = int(node_name[len('node'):])
            hostname, port = params.strip().split(':', maxsplit=1)
            logger.debug((node_number, hostname, port))
            nodes[node_number] = Peer(hostname=hostname, port=int(port))
    return nodes


nodes = None


if __name__ == '__main__':
    # Setup argument parser
    parser = argparse.ArgumentParser(description='Run a Raft node')
    parser.add_argument('node_number', type=int,
                        help='The number of node to run')
    parser.add_argument('--config', nargs='?', default='raft_config.yaml')
    args = parser.parse_args()
    logger.debug(args)
    # Parse nodes from configuration
    nodes = parse_raft_config(args.config)
    logger.debug(nodes)
    if args.node_number not in nodes:
        raise Exception('Node number does not exist in the configuration')
    node = nodes[args.node_number]
    nodes.pop(args.node_number)

    s = ThreadPoolServer(RaftServer(id=args.node_number, peers=nodes),
                         hostname=node.hostname, port=node.port)
    s.start()
