import rpyc
conn = rpyc.connect("localhost", 18812)
conn.root.append_entries_rpc()
