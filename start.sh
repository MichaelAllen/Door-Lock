# Start PiGPIO
pigpiod

# Secure lock
gpio mode 2 out
gpio write 2 1

# Start alarm (Untill app stops it)
gpio mode 22 out
gpio write 22 0

# Start the app
/opt/door/door.py
