import rpyc
import subprocess
import signal
import time
import logging

from raft import parse_raft_config

# Helper functions

def start_node(node_number):
    proc = subprocess.Popen(['python', 'raft.py', str(node_number)],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    return proc


def count_leaders(nodes):
    leaders = 0
    for i, node in nodes.items():
        try:
            conn = rpyc.connect(node.hostname, node.port)
            result = conn.root.is_leader()
            if result:
                leaders += 1
        except (ConnectionError, EOFError):
            pass
    return leaders


def find_leader(nodes):
    leaders = 0
    for i, node in nodes.items():
        try:
            conn = rpyc.connect(node.hostname, node.port)
            result = conn.root.is_leader()
            if result:
                return i
        except (ConnectionError, EOFError):
            pass


def test_elect_single_leader():
    nodes = parse_raft_config('raft_config.yaml')
    try:
        # Start the 5 nodes
        node_processes = {}
        for i in nodes:
            proc = start_node(i)
            node_processes[i] = proc

        # Sleep for 15 seconds
        time.sleep(15)

        # A single leader should be elected
        leaders = count_leaders(nodes)
        assert leaders == 1

    finally:
        for proc in node_processes.values():
            proc.send_signal(signal.SIGINT)
            proc.wait()


def test_senario_1():
    nodes = parse_raft_config('raft_config.yaml')
    try:
        node_processes = {}
        # Start the first node
        logging.info('Starting the first node...')
        proc_0 = start_node(0)
        node_processes[0] = proc_0
        # Sleep for 15 seconds
        logging.info('Sleep for 15 seconds...')
        time.sleep(15)
        # No leader should be elected
        leaders = count_leaders(nodes)
        assert leaders == 0
        logging.info('No leader elected')

        # Start the second node
        logging.info('Starting the second node...')
        proc_1 = start_node(1)
        node_processes[1] = proc_1
        # Sleep for 15 seconds
        logging.info('Sleep for 15 seconds...')
        time.sleep(15)
        # No leader should be elected
        leaders = count_leaders(nodes)
        assert leaders == 0
        logging.info('No leader elected')

        # Start the third node
        logging.info('Starting the third node...')
        proc_2 = start_node(2)
        node_processes[2] = proc_2
        # Sleep for 15 seconds
        logging.info('Sleep for 15 seconds...')
        time.sleep(15)
        # A single leader should be elected
        leaders = count_leaders(nodes)
        logging.info(leaders)
        assert leaders == 1
        logging.info('A single leader is elected')

        # Start the fourth node
        logging.info('Starting the fourth node...')
        proc_3 = start_node(3)
        node_processes[3] = proc_3
        # Sleep for 15 seconds
        logging.info('Sleep for 15 seconds...')
        time.sleep(15)
        # A single leader should remain
        leaders = count_leaders(nodes)
        logging.info(leaders)
        assert leaders == 1
        logging.info('One leader')

        # Start the fifth node
        logging.info('Starting the fifth node...')
        proc_4 = start_node(4)
        node_processes[4] = proc_4
        # Sleep for 15 seconds
        logging.info('Sleep for 15 seconds...')
        time.sleep(15)
        # A single leader should remain
        leaders = count_leaders(nodes)
        logging.info(leaders)
        assert leaders == 1
        logging.info('One leader')

        # Kill the leader, 4 remain
        leader_number = find_leader(nodes)
        logging.info("Killing the leader that has number %s", leader_number)
        node_processes[leader_number].send_signal(signal.SIGINT)
        node_processes[leader_number].wait()
        logging.info('Sleep for 15 seconds...')
        time.sleep(15)
        # A single leader must be elected
        leaders = count_leaders(nodes)
        logging.info(leaders)
        assert leaders == 1
        logging.info('A single leader is elected')

        # Kill the leader, 3 remain
        leader_number = find_leader(nodes)
        logging.info("Killing the leader that has number %s", leader_number)
        node_processes[leader_number].send_signal(signal.SIGINT)
        node_processes[leader_number].wait()
        logging.info('Sleep for 15 seconds...')
        time.sleep(15)
        # A single leader must be elected
        leaders = count_leaders(nodes)
        logging.info(leaders)
        assert leaders == 1
        logging.info('A single leader is elected')

        # Kill the leader, 2 remain
        leader_number = find_leader(nodes)
        logging.info("Killing the leader that has number %s", leader_number)
        node_processes[leader_number].send_signal(signal.SIGINT)
        node_processes[leader_number].wait()
        logging.info('Sleep for 15 seconds...')
        time.sleep(15)
        # No leader should be elected
        leaders = count_leaders(nodes)
        logging.info(leaders)
        assert leaders == 0
        logging.info('No leader elected')

    finally:
        for proc in node_processes.values():
            proc.send_signal(signal.SIGINT)
            proc.wait()
