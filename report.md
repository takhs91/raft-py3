# Raft implementation in Python 3

## Initial Proposal
* Implement a correct version of raft in python 3
* I will try to write an accompanying test suite to make sure its correct
with as much as possible code coverage
* I will try to implement it in a way it could be ran in either one node
(simulation style) or multiple nodes
* If I manage to finish it early enough (early June-to mid June) I plan on
either implementing a fault tolerant, strongly consistent key value store
on top similar to zookeeper etcd, etc. or concentrate on measurements
experiments etc.


Demonstration
* I will present and explain the most interesting parts of the code
* I will do a demo of various interesting cases of correct runs with
different numbers of nodes or failures, network partitions etc.
* I will present any measurements if done


## Report

### Timeline 

1. At the beginning a spent quite some time studying the paper, `Figure 2` was the most helpful asset in developement since it always served as a cheat sheet.
2. I spent time studying other raft implementation mostly in other languages than the one I chose in order not to get biased about my implementation. [This](https://eli.thegreenplace.net/2020/implementing-raft-part-1-elections/) golang implementation that came with an accompanying blog was very helpful
3. I was thinking how to construct the project in way that I could simulate/mock rpc calls in order to add delays, drop links create partitions etc. but I decided this was very time consuming and that I was missing parts of the pircture to do it right, thus I decided using a real RPC library and leave that for later
4. I had to decide for an RPC library. I was between `xmlrpc` from the standard python library and `RPyc` and decided to go with the second as it had nice documentation
5. Very soon I had to choose a concurrency method, I had to choose between using event loop based coroutines such those provided by (`asycio`  `gevent`,`eventlet`) or threads. I have decided to go with threads, since I have decided I don't have enough time to learn to use coroutines. I have to mentiont that in CPython because of the [GIL](https://realpython.com/python-gil/) essentially on thread is executing at the time. This doesn't mean there are no race conditions though since threads might switch execution accross series of operation that should be atomic. Thus using synchronization primitives such as locks is required when altering shared objects
6. Implemetation finally started
7. Firstly I implemented only the Leader Election. That means I had to implement most of the Follower logic and its election timer, the Candidate logic and its timer, a small part of the Leader logic, the RequestVote RPC and a very simple AppendEntries RPC.
8. After a lot of testing and  debugging this was ready. At this time I decided to leave the cluster membership changes and log compaction steps out of scope
9. I then implemented the Log replication section and the election restriction. I had to fill all the things I skiped before. I also implemeted a simple RPC for accepting client requests. The requests are dummy (contain no actual commands) and thus are also not appied to a a state machine. Also my simple client sbmit rpc returns before the command is commited. Making this to block till command is commited shouldn't be very difficult to implement
10. I spent a lot time debugging and testing on those
11. Finally I implemented the state peristance part


### Completed tasks
* The basic Raft algorithm is implemented
* After extensive manual testing I believe its correct
* The implemention is possible to run in either one or multiple machines

### Unfinished tasks
* Automated tests
* Measurments
* Real commands and state machine

# Evaluation
Manual testing of various scenarios mostly related to node crashes was done

Example test for leader election using 5 nodes:
1. Start the first node, its timer will expire and become a candidate
2. Start a second node, they cannot elect a leader
3. Start a third node, after a while a leader is elected
4. Add a fourth node, the leader doesn't change
5. Add the fifth node, the leader doesn't change
6. Crash the leader, the four remaining nodes elect a new leader
7. Crash the leader, the three remaining nodes elect a new leader
8. Crash the leader, the two remaining nodes don't elect a new leader
