import rpyc
import argparse

from raft import parse_raft_config

# Setup argument parser
parser = argparse.ArgumentParser(description='Run a Raft node')
parser.add_argument('node_number', type=int,
                    help='The number of node to run')
parser.add_argument('--config', nargs='?', default='raft_config.yaml')
args = parser.parse_args()

# Parse nodes from configuration
nodes = parse_raft_config(args.config)
if args.node_number not in nodes:
    raise Exception('Node number does not exist in the configuration')
node = nodes[args.node_number]

conn = rpyc.connect(node.hostname, node.port)
result = conn.root.submit_rpc('')
print(result)
