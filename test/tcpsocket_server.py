#!/usr/bin/python
#====================================================================================
# Simple TCP/IP socket server for sending and receiving data.
#

import socket
import time
import sys
import os
import threading

def prompt() :
    sys.stdout.write('$$$ ')
    sys.stdout.flush()

class ReceiveHandler(threading.Thread):
   # Subslass to handle incoming messages from client.
   # Handling incoming messages from server

   def __init__(self, xxx):
      threading.Thread.__init__(self)
      self.xxx = xxx
      self.started = None

   def run(self):
      # Excutes when thread started.
      # Overriding python threading.Thread.run()
      if self.started == True:
         print("ReceiveHandler already started")
         return None
      print("ReceiveHandler start running")
      while True:
         self.started = True
         message = conn.recv(1024)   # wait for message
         if not message:
            print("error receiving data; socket connection lost")
            break
         print("Received: " + message)
         prompt()
      # end while

      self.started = False
      print("ReceiveHandler stopped")
      prompt()
      return None
   # def run(self)

# CLASS ReceiveHandler

class ConsoleHandler(threading.Thread):
   # Subslass to handle console input from user.

   def __init__(self):
      threading.Thread.__init__(self)
      self.started = None

   def run(self):
      # Excutes when thread started. Overriding python threading.Thread.run()
      if self.started == True:
         print("ConsoleHandler already started")
         return None
      print("ConsoleHandler start running")

      while True:
         self.started = True
         prompt()
         comm = sys.stdin.readline()   # blocked until user entered a message

         if comm.startswith('q'):
            os._exit(1)  # quit

         elif comm.startswith('h'):
            printHelp()

         elif comm.lower().startswith('chat'):
            # *** outgoing chat message to client ***
            if len(comm.split()) == 1:
               continue
            if len(comm.split()) > 1:
               _, msg = comm.split(' ', 1)  # strip first word
               msg = msg.strip()            # trim whitespace
               try:
                  conn.send(msg)
                  print("snd CHAT: " + msg)
               except:
                  print("Error: no connection")

         elif comm.startswith('send'):
            # *** test1 ***
            msg = "Hello World"
            try:
               conn.send("Hello World" + "\0")
               print("snd " + msg)
            except:
               print("Error sending message: " + msg)

         else:
            try:
               msg = comm + "\0"
               conn.send(msg)
               print("snd " + msg)
            except:
               print("Error sending message: " + msg)
      # end while

      self.started = False
      print("ConsoleHandler stopped")
      return None
   # def run(self)

# CLASS ConsoleHandler

def printHelp():
   help = []
   help.append("Use one of these commands:  " )
   help.append("q:                quit" )
   help.append("h:                this help info" )
   help.append("send:             send test string" )
   help.append("chat <msg>:       send message <msg>  " )
   help.append("---:              send input if command not found " )

   print(" " + "_"*60)
   for line in help:
      print("|" + (" " + line).ljust(60) + "|")
   print("|" + "_"*60 + "|")

   return None
# def printHelp()


if __name__ == "__main__":
   print("||==============================||")
   print("|| Simple tcp socket server     ||")
   print("||==============================||")

   host = '127.0.0.1'
   port = 27531       # default damexchange

   try:
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
   except socket.error as msg:
      sock = None
      print('Could not open socket: ' + str(msg) )
      sys.exit(1)

   try:
      sock.bind((host, port))
      sock.listen(1)
   except socket.error as msg:
      sock.close()
      sock = None
      print('Could not open socket: ' + str(msg) )
      sys.exit(1)

   conn = None
   while True:
      if conn is None:
         print "[Waiting for client connection at %s for port %s ...]" %(host, str(port)) 
         conn, addr = sock.accept()            # Halts
         print 'Got connection from address ', addr
      else: break

   # use 2 threads to simultaneous listen to incoming messages and console input
   xxx = 333
   tReceiveHandler = ReceiveHandler(xxx)  # Thread subclass instance
   tConsoleHandler = ConsoleHandler()     # Thread subclass instance
   tReceiveHandler.start()
   tConsoleHandler.start()

#==============================================================================

