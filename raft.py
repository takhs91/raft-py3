import logging
import random
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


class RaftServer(Service):
    def __init__(self):
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
        self.election_timer = threading.Thread(
            target=self.candidate_election_timeout,
            args=('candidate_election_timeout',),
            daemon=True,
        )
        self.election_timer.start()
        self.candidate_loop = threading.Thread(
            target=self.candidate_loop,
            args=('candidate_loop',),
            daemon=True,
        )
        self.candidate_loop.start()

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
                logger.info("Thread %s: Timed out: Starting new election", name)
                self.candidate_timer_expired_event.set()
                self.candidate_timer_reset_event.clear()
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
            self.candidate_timer_expired_event.wait()
            self.candidate_timer_expired_event.clear()

    def exposed_append_entries_rpc(self):
        """Append Entries RPC
        """
        logger.info("Called the Append Entries RPC")
        self.reset_event.set()

    def exposed_is_leader(self):
        return False


if __name__ == '__main__':
    s = ThreadPoolServer(RaftServer(), port=18871)
    s.start()
