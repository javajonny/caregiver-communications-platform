
import bcrypt

password = b"XXXXXXXXXXXXX!"
# Generate salt and hash
hashed = bcrypt.hashpw(password, bcrypt.gensalt(rounds=12))
print(hashed.decode('utf-8'))
