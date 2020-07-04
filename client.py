import rpyc
conn = rpyc.connect("localhost", 18812)
result = conn.root.submit_rpc('')
print(result)