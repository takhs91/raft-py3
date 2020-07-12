# raft-py3

A python3 implementation of the Raft distributed consensus algorithm.

It utilizes the RPyC librabry for RPC and the standard threading library for concurrency.

## Usage

Python 3.7 is required

Install depedencies
```
pip install -r requirements.txt
```

Run a raft node
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