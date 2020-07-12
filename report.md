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
4. I had to decide for an RPC library. I was between `xmlrpc` from the standard python library and `RPyc` and decided to go with the second as it had nice documentation and offered async requests
5. Very soon I had to choose a concurrency method, I had to choose between using event loop based coroutines such those provided by (`asycio`, `gevent`, `eventlet`) or threads. I have decided to go with threads, since I have decided I don't have enough time to learn to use coroutines. I have to mentiont that in CPython because of the [GIL](https://realpython.com/python-gil/) essentially on thread is executing at the time. This doesn't mean there are no race conditions though since threads might switch execution accross series of operation that should be atomic (e.g fetch and update). Thus using synchronization primitives such as locks is required when altering shared objects
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


# Architechture/Implementation Details

The `RaftServer` class is the basis. It subclasses the rpyc [Service](https://rpyc.readthedocs.io/en/latest/docs/services.html) class.
Any methods starting with `exposed_` will be exposed as RPC, in our case they are the
* exposed_submit_rpc
* exposed_request_vote_rpc
* exposed_append_entries_rpc

The service is exposed using a [ThreadPoolServer](https://rpyc.readthedocs.io/en/latest/api/utils_server.html#rpyc.utils.server.ThreadPoolServer) that means its rpc request will be handled by one of the threads available in the ThreadPool.

Except the threads owned byt the ThreadPoolServer to serve incoming rpc calls the `RaftServer` on its constructor start starts 4 more threads
that run the following functions

1. `election_timeout` which is the function running the timer that will make a FOLLOWER switch to candidate
2. `candidate_election_timeout` which is the timer that uppon expiration makes a candidate to start a new election.
3. `candidate_loop` which is the candidate logic
4. `leader_loop` which is the logic of the leader

All those functions contain loops that run forever but may block uppon different events.
For example the leader loop will stop running if `leader_event` is not set.
This event for example will get set by the candidate loop if it manages to collect the majority of votes.

The helper method `switch_state_to(self, state)` is used to set the events appropriately

Given I had more time I would try to rewrite this with only two threads.
One for the candidate timer and one for the candidate+leader+follower timer.
At the beggining a just though it would be easier to use a different thread for each one and just make sure to sync them right.

There are parts were the leader and the candidate has to send RPC to the other nodes asynchronously.
One way it could be done was with different threads or a thread pool, although I decided to implement that in
the same loop utilizing the asyncronous operation of RPyC as described [here](https://rpyc.readthedocs.io/en/latest/tutorial/tut5.html)
The requests are issued in a first loop for all the nodes and the "AsyncResult" are saved in an appropriated data structure.
A second loop is responsible for checking if any of the results are ready and do the appropriate actions.

One more thing that would have to be improved its the fact that the leader sends AppendEntriesRPC in fixed intervals only.
This could be optimized in a way to send AppendEntriesRPC needed to serve a client request immidiately and also send some on fixed
intervals or using a timer based logic (if haven't sent any for x time then send some).

Also as stated in the timeline section the commands are currently dummy and there is no state machine. Furthemore the client rpc returns
immediately before  the request gets commited. This would probably need a new event set per request, that the leader loop would set when the commit index would reach the index of the request.

The state is saved to JSON using the `persist_state` and `load_state` methods


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

Example test for log replication
1. Start all nodes
2. Send some client commands, watch them get replicated
3. Crash some nodes
4. Issue more client commands, watch them replicate
5. Bring the crashed nodes up, the leader will replicate any commands they missed when down

Test for log replication with log conflicts
1. Bring up all nodes
2. Crash them all except the leader and one more
3. Issue some requests, the will be replicated but won't be commited
4. Crash them both
5. Restart the previously 3 crashed nodes
6. Send some request to the new leader, the will be replicated and commited
7. Restart the previsously 2 crashed nodes
8. The leader will replace their uncommited logs that conflict with the leaer log