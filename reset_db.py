import os

if os.path.exists('bedtime.db'):
    os.remove('bedtime.db')
print("Database reset complete!")
