import rpyc
conn = rpyc.connect("localhost", 18871)
conn.root.append_entries_rpc()
