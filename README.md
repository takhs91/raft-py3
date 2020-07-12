# raft-py3

A python3 implementation of the Raft distributed consensus algorithm.

It utilizes the RPyC librabry for RPC and the standard threading library for concurrency.

## Usage

Python 3.7 is required

Install depedencies
```
pip install -r requirements.txt
```

Run a raft node, the argument is the node number as defined in the config file
```
python raft.py 0
```

Ιssue a client request to a raft node
```
python client.py 0
```

To run tests
```
pip install pytest
pytest
```

The sample config file
```
node0: localhost:18812
node1: localhost:18813
node2: localhost:18814
node3: localhost:18815
node4: localhost:18816
```
