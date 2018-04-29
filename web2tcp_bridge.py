#!/usr/bin/env python

"""
|===================================================================================
| Web2Tcp: bridging Websockets and Tcp Sockets                                      |
|===================================================================================
| Problem: how can a browser client communicate with a Tcp Socket server?
| There is no simple way to create Tcp Sockets in Javascript on a browser side.
| Webpages uses the Websocket protocol to communicate with a server.
|
| A solution is this application. It translates messages from the Websocket protocol
| to the Tcp Socket protocol and vice versa.
| I call it a bridge server because it acts as a bridge for messages between the
| Websocket and the Tcp Socket protocol.
|
| The bridge server has two parts:
| 1. a websocket server to receive messages from browser clients.
| 2. a Tcp Socket client to receive messages from a Tcp Socket server.
|
| Connection schema:   client(s) <====> bridge <====> server
| More than one client can open a connection with the bridge server.
|
| Start the application from a terminal: python web2tcp_bridge.py
| 
| (c) Arthur Kalverboer 2018
====================================================================================
"""

import re, sys, os, time
import threading
import logging
import socket
from web2tcp_websocketserver import WebsocketServer

# === CONSTANTS ===
VERSION = "2018.04.29"  # initial release: version 2018.05.01
APPNAME = {'short':'Web2Tcp', 'long':'Web2Tcp Bridge', 'github': 'web2tcp_bridge'}
SYSLOG_FILE = 'web2tcp_xsys.log'
MSGLOG_FILE = 'web2tcp_xmsg.log'

WS_HOST = '127.0.0.1' # default host address for WEB2TCP bridge server ('localhost')
WS_PORT = 27532       # default port connection ws_client and ws_server

TCP_HOST = '127.0.0.1' # default host address for tcp_server ('localhost')
TCP_PORT = 27531       # default port connection tcp_client and tcp_server
                       # 27531 is the default port for DamExchange (DXP) protocol

TERMINATOR = "\0"      # message terminator for tcp-connections (null character)
                       # websockets is message based protocol (no terminator needed)
                       # tcp-sockets is stream based protocol, terminator needed 
MAX_MSG_LEN = 200      # Max length of received messages (char); msg will be truncated
#===================================================================================

def prompt() :
    sys.stdout.write('>>> ')
    sys.stdout.flush()

def initLogging():
   # Log names: ALERT, SYS
   # Levelnames: DEBUG, INFO, WARNING, ERROR and CRITICAL.
   global syslog, msglog, alert

   syslog = logging.getLogger('SYS')   # system logfile
   msglog = logging.getLogger('MSG')   # message logfile
   alert  = logging.getLogger('ALERT') # console + logfile

   formatter1 = logging.Formatter('%(levelname)-8s: %(message)s')
   formatter2 = logging.Formatter("%(name)-6s %(levelname)-6s %(asctime)s: %(message)s")
   formatter3 = logging.Formatter('%(name)-6s %(levelname)-6s: %(message)s')
   formatter4 = logging.Formatter("%(asctime)s: %(message)s")
   formatter5 = logging.Formatter("%(levelname)-6s %(asctime)s: %(message)s")

   hConsole = logging.StreamHandler()
   hConsole.setFormatter(formatter1)
   hFileSys = logging.FileHandler(filename=SYSLOG_FILE, mode='a')
   hFileMsg = logging.FileHandler(filename=MSGLOG_FILE, mode='a')
   hFileSys.setFormatter(formatter5)
   hFileMsg.setFormatter(formatter4)

   alert.setLevel(logging.INFO)
   alert.addHandler(hConsole)
   alert.addHandler(hFileSys)

   syslog.setLevel(logging.DEBUG)
   syslog.addHandler(hFileSys)
   msglog.setLevel(logging.DEBUG)
   msglog.addHandler(hFileMsg)

   return None
#  initLogging()

def clearLogFiles():
   with open(SYSLOG_FILE, 'w'):
      pass
   with open(MSGLOG_FILE, 'w'):
      pass
   return None
#  clearLogFiles()

def showStatus():
   status = []
   status.append("STATUS INFO" )
   status.append("")
   if mySock.sock != None:
      status.append("Tcp socket connection opened.")
      status.append("    host %s and port %s"  % (current.tcp_host, current.tcp_port))
   else:
      status.append("Tcp socket connection closed")
   if tWebsocketHandler.server != None:
      status.append("Websocket connection opened.")
      status.append("    host %s and port %s"  % (current.ws_host, current.ws_port))
   else:
      status.append("Websocket connection closed")
   print(" " + "_"*60)
   for line in status:
      print("|" + (" " + line).ljust(60) + "|")
   print("|" + "_"*60 + "|")
   return None
#  showStatus()

class State:
   # A state of the application
   def __init__(self):
      self.state = {}
      self.state['ws_host'] = "127.0.0.1"
      self.state['ws_port'] = 27532
      self.state['tcp_host'] = "127.0.0.1"
      self.state['tcp_port'] = 27531
# END class State 

class MySocket:
   # Socket class
   # New since Python 2.3: sock = socket.create_connection( (host,port), timeout=10 )
   #    It will try to resolve hostname for both AF_INET and AF_INET6
   #

   def __init__(self):
      self.sock = None

   def test(self, txt):
      print(txt)

   def open(self):
      try:
         self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      except:
         self.sock = None
         raise Exception("socket exception: failed to open")
      return self
   # def open(self)

   def connect(self, host, port):
      self.sock.settimeout(2)  # timeout for connection
      try:
         self.sock.connect((host, port))
      except socket.error as msg:
         #self.sock.close()
         self.sock = None
         raise Exception("tcp connection exception: failed to connect")
      if self.sock != None:
         self.sock.settimeout(None)  # default
      return self
   # def connect(self)

   def send999(self, imsg):
      #sent = self.sock.send(msg)  # simple send
      msg =  imsg + TERMINATOR
      msgLen = len(msg)
      totalsent = 0
      while totalsent < msgLen:
         try:
            sent = self.sock.send(msg[totalsent:])
         except:
            raise Exception("send exception: no tcp connection")
            return None
         if sent == 0:
            raise Exception("send exception: socket tcp connection broken")
            break
         totalsent = totalsent + sent
      # end while
      return None
   # def send999(self)

   def send(self, msg):
      # Send message to tcp-server
      try:
         self.sock.send(msg + TERMINATOR)
      except:
         raise Exception("send exception: no tcp connection")
      return None
   # def send(self)

   def receive(self):
      # Receive messages from tcp-socket server
      # Chunks of the stream is concatenated until last char is the TERMINATOR
      # The concatenated chunks contain multiple messages (but often just one)
      # Returns list of received messages
      recvdString = ""  # Received string
      while True:
         # Collect message chunks until null character found
         try:
            chunk = self.sock.recv(1024)
         except:
            raise Exception("receive exception: no tcp connection")
            return None

         if chunk == "":
            raise Exception("receive exception: socket tcp connection broken")
            return None
         recvdString += chunk
         if recvdString.strip()[-1] == TERMINATOR: break   # stop if last char is TERM

      #print("final received string: " + recvdString)

      recvdMessages = recvdString.split(TERMINATOR)
      recvdMessages.pop()  # remove last item (is empty)
      return recvdMessages
   # def receive(self)

# *** END class MySocket ***

class WebsocketHandler(threading.Thread):
   # Subslass of Thread to handle events of the WebsocketServer.
   # To receive and send messages from/to a browser webscocket client.

   def __init__(self):
      threading.Thread.__init__(self)
      self.server = None
      self.host = WS_HOST
      self.port = WS_PORT
      return None
   # def __init__()

   def onClientNew(self, iClient, iServer):
      # Called by server for every client connecting to server (after handshake)
      # ** PRIVATE **
      print("\n" + "New client connected and was given id %d" % iClient['id'])
      prompt()
      ###self.server.send_message_to_all( "#Hey all, a new client has joined us" )
      ###self.server.send_message(iClient, "#ws connection opened")
      return None
   # def onClientNew()

   def onClientLeft(self, iClient, iServer):
      # Called by server for every client disconnecting from bridge (ws-server)
      # ** PRIVATE **
      print("\n" + "Client(%d) disconnected from bridge (ws-server)" % iClient['id'])
      prompt()
      return None
   # def onClientLeft()

   def onReceive(self, iClient, iServer, iMessage):
      # RECEIVE MESSAGE BY WS_SERVER FROM WS_CLIENT
      # Runs when bridge (ws-server) receives a message send by a ws-client
      # ** PRIVATE **
      if len(iMessage) > MAX_MSG_LEN:
         iMessage = iMessage[:MAX_MSG_LEN]+'...'
      msg_info = "client(%d) ==> bridge:" % iClient['id']
      msg_info = msg_info.ljust(22)  + " " + iMessage 
      print("\n" + "Message from " + msg_info)
      msglog.info(msg_info)

      # Send message back from server to other clients
      # ************* TEST TEST TEST ***
      """
      msg_info = "bridge ==> clients:".ljust(22) + " " + iMessage
      print("\n" + "Message from " + msg_info)
      msglog.info(msg_info)
      self.server.send_message_to_other(iClient, iMessage)
      """
      # ************* TEST TEST TEST ***

      # FORWARD MESSAGE FROM WS_CLIENT TO TCP_SERVER
      try:
         mySock.send(iMessage)
         msg_info = "bridge ==> server:".ljust(22) + " " + iMessage
         print( "Message from " + msg_info )
         msglog.info(msg_info)
      except:
         err = sys.exc_info()[1]
         print( "Error forwarding message to tcp-server: %s" % err )

      prompt()
      return None
   # def onReceive()

   def send(self, iClient, iMessage):
      # Send message to client iClient. NOT USED (send_to_all USED)
      msg_info = "bridge ==> client(%d):".ljust(22) +  " " + iMessage  % iClient['id']
      print("\n" + "Message from " + msg_info)
      prompt()
      msglog.info(msg_info)
      self.server.send_message(iClient, iMessage)
      return None
   # def send()

   def send_to_all(self, iMessage):
      # Send message to all connected clients Use it for calls from outside.
      self.server.send_message_to_all(iMessage)
      return None
   # def send_to_all()

   def run(self):
      # Handling events, sending and receiving messages of websocket server.
      # Executes when thread started. Overriding python threading.Thread.run()
      # Exception handling is annoying for the start of a thread. Leave it as.
      # ** PRIVATE **
      self.server = WebsocketServer(self.port, self.host)
      self.server.set_fn_new_client(self.onClientNew)
      self.server.set_fn_client_left(self.onClientLeft)
      self.server.set_fn_message_received(self.onReceive)
      self.server.run_forever()   # WAIT...
      return self.server
   # def run(self)

# CLASS WebsocketHandler

def runConsoleHandler(stack):
   # Handling console input from user.
   # Parameter stack: array of initial actions ( stack.append("help") )
   syslog.info("Application started")
   msglog.info("Application started")

   global mySock, lock
   while True:
      if len(stack) > 0:
         comm = stack.pop()
         syslog.info("Action from stack: %s" % comm)
      else:
         prompt()
         comm = sys.stdin.readline()   # blocked until user entered a message

      if comm.lower().startswith('q'):  # quit
         syslog.info("Application terminated by user " )
         msglog.info("Application terminated by user " )
         os._exit(1)   # does no cleanups

      elif comm.lower().startswith('h') or comm.startswith('?'):
         syslog.info("Command show help")
         lock.acquire()   # LOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCK
         # Set lock to prevent printing by incoming messages while printing help
         printHelp()
         lock.release()   # LOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCK

      elif comm.lower().startswith('info'):
         syslog.info("Command show status of application: %s" %comm.strip() )
         showStatus()

      elif comm.lower().startswith('clear'):
         clearLogFiles()
         print("Log file %s and %s cleared " % (SYSLOG_FILE, MSGLOG_FILE) )
         syslog.info("Log file %s and %s cleared " % (SYSLOG_FILE, MSGLOG_FILE) )

      elif comm.lower().startswith('start'):
         if tWebsocketHandler.server != None:
            # prevent starting websocket handler twice
            print("Websocket server already started")
            continue
         host, port = WS_HOST, WS_PORT  # default
         words = comm.split()
         if len(words) == 2: _,host = words
         if len(words) == 3: _,host,port = words
         try:
            tWebsocketHandler.host = host
            tWebsocketHandler.port = int(port)
            tWebsocketHandler.start()   # exec run() of thread
            ###print( "xxx Websocket server started xxx " )
            info_txt = "Listening at %s on port %s for messages from browser clients ..." %(host,port)
            msglog.info(info_txt)
            syslog.info( "Websocket server started at %s on port %s" %(host,port) )
            current.ws_host = host
            current.ws_port = port
         except:
            err = sys.exc_info()[1]
            print( "Error trying to start websocket server: %s" % err )
            continue

      elif comm.lower().startswith('conn'):
         # *** connect to remote host ***
         if mySock.sock != None:
            print("Already connected")
            continue
         if tReceiveHandler.isListening:
            print("Receivehandler already listening; first restart application to connect")
            continue

         host, port = TCP_HOST, TCP_PORT  # default
         words = comm.split()
         if len(words) == 2: _,host = words
         if len(words) == 3: _,host,port = words
         try :
            mySock.open()
            mySock.connect(host, int(port))  # with timeout
            info_txt = "Listening at %s on port %s for messages from server ..." %(host,port)
            print(info_txt)
            msglog.info(info_txt)
            syslog.info( "Bridge connected to tcp-server at %s on port %s" %(host,port) )
            current.tcp_host = host
            current.tcp_port = port
         except:
            #mySock.sock.close()
            mySock.sock = None
            err = sys.exc_info()[1]
            print( "Error trying to connect to tcp-server: %s" % err )
            continue

         if mySock.sock != None:  # check connected
            # prevent starting receivehandler twice
            if not tReceiveHandler.isListening: tReceiveHandler.start()

      elif comm.lower().startswith('chats'):
         # *** outgoing CHAT message to TCP_Server ***
         if len(comm.split()) == 1:
            continue
         if len(comm.split()) > 1:
            _, msg = comm.split(' ', 1)  # strip first word
            msg = msg.strip()            # trim whitespace
            syslog.info("Send chat message to tcp_server: %s" %comm.strip() )
            try:
               mySock.send(msg)
               msg_info = "bridge(*) ==> server:".ljust(22) + " " + msg
               print("Message from " + msg_info)
               msglog.info(msg_info)
               syslog.info("Send chat message to server: %s" %comm.strip() )
            except:
               err = sys.exc_info()[1]
               print( "Error sending chat message to tcp_server: %s" % err )
               continue

      elif comm.lower().startswith('chatc'):
         # *** outgoing CHAT message to all WS clients ***
         if tWebsocketHandler.server == None:
            print("Websocket server not started")
            continue

         if len(comm.split()) == 1:
            continue
         if len(comm.split()) > 1:
            _, msg = comm.split(' ', 1)  # strip first word
            msg = msg.strip()            # trim whitespace
            try:
               tWebsocketHandler.send_to_all(msg)
               msg_info = "bridge(*) ==> clients:".ljust(22) + " " + msg
               print("Message from " + msg_info)
               msglog.info(msg_info)
               syslog.info("Send chat message to clients: %s" %comm.strip() )
            except:
               err = sys.exc_info()[1]
               print( "Error sending chat message to clients: %s" % err )
               continue

      elif comm.startswith('test0'):
         # *** TEST TEST TEST ***
         syslog.info("Command test: %s" %comm.strip() )
         t0 = time.time()
         for i in range(1,100):
            i = i + 2
         t1 = time.time()
         print("Time elapsed for test: " + str(t1 - t0)  )

      elif comm.startswith('test1'):
         # *** TEST TEST TEST ***
         syslog.info("Command test: %s" %comm.strip() )
 
         alert.info("Alert > TEST MESSAGE")
         syslog.info("Sys > TEST MESSAGE")

         msg = "Hello World"
         try:
            mySock.send(msg)
            print("snd TEST: " + msg)
         except:
            err = sys.exc_info()[1]
            print( "Error %s" % err )

      #===================================================================================
      else:
         syslog.info("Command unknown: %s" %comm.strip() )
         print("Unknown command, type h for help: %s" %comm.strip() )
         ### stack.append('H')

   # end while console input

   print("ConsoleHandler stopped")
   return None
# def runConsoleHandler()

def printHelp():
   help = []
   help.append("Use one of these commands:  " )
   help.append("")
   help.append("q:                quit" )
   help.append("h:                this help info" )
   help.append("info:             show status of application" )
   help.append("clear:            clear log files" )
   help.append("")
   help.append("start <host> <port>:  " )
   help.append("                  start websocket server" )
   help.append("                  default host %s and port %s " %(WS_HOST, WS_PORT) )
   help.append("")
   help.append("connect <host> <port>: " )
   help.append("                  connect to tcp server " )
   help.append("                  default host %s and port %s "  %(TCP_HOST, TCP_PORT) )
   help.append("")
   help.append("chatS <msg>:      send chat message to tcp server " )
   help.append("chatC <msg>:      send chat message to all browser clients " )

   print(" " + "_"*60)
   for line in help:
      print("|" + (" " + line).ljust(60) + "|")
   print("|" + "_"*60 + "|")

   return None
# def printHelp()

class ReceiveHandler(threading.Thread):
   # Subslass of Thread to handle incoming messages from TCP Socket server.

   def __init__(self):
      threading.Thread.__init__(self)
      self.isListening = False

   def run(self):
      # Handling incoming messages from socket server.
      # Excutes when thread started. Overriding python threading.Thread.run()

      syslog.info("ReceiveHandler started")
      global mySock, lock, tWebsocketHandler
      self.isListening = True
      syslog.info("Starts listening to TCP socket server" )
      while True:
         try:
            recvdMessages = mySock.receive()   # wait for received messages
         except:
            err = sys.exc_info()[1]
            print( "Error %s" % err )
            break

         # RECEIVE MESSAGE BY BRIDGE (TCP_CLIENT) FROM TCP_SERVER
         lock.acquire()   # LOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCK

         for message in recvdMessages:
            # Use strip to remove all whitespace at the start and end of a message.
            # Including spaces, tabs, newlines and carriage returns.
            message = message.strip()
            if len(message) > MAX_MSG_LEN:
               message = message[:MAX_MSG_LEN]+'...'   # truncate

            msg_info = "server ==> bridge:".ljust(22) + " " + message
            print("\n" + "Message from " + msg_info)
            msglog.info(msg_info)

            # FORWARD MESSAGE FROM TCP_SERVER TO WS_CLIENT
            if tWebsocketHandler.server == None:
               print("Error forwarding message: websocket server not started")
            else:
               try:
                  tWebsocketHandler.send_to_all(message)   # to all ws-clients
                  msg_info = "bridge ==> clients:".ljust(22) + " " + message
                  print("Message from " + msg_info)
                  msglog.info(msg_info)
               except:
                  err = sys.exc_info()[1]
                  print( "Error forwarding message to ws-client: %s" % err )

         lock.release()   # LOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCKLOCK
         prompt()
      # end while listening

      self.isListening = False
      mySock.sock = None
      syslog.error("Listening to tcp-server stopped; tcp connection broken")
      print("Tcp connection broken; receiving messages from server stopped. ")
      prompt()
      return None
   # def run(self)

# CLASS ReceiveHandler

if __name__ == '__main__':
   print("||==================================================================||")
   print("|| WEB2TCP: bridge server between websocket and tcp-socket traffic  ||")
   print("||==================================================================||")

   mySock = MySocket()     # global, singleton
   lock = threading.Lock() # global
   initLogging()           # globals: syslog
   current = State()       # global

   # use 2 threads to simultaneous websocket and tcp-socket traffic
   tReceiveHandler = ReceiveHandler()   # Thread subclass instance. Start when connected.
   tWebsocketHandler = WebsocketHandler() 

   if len(sys.argv) == 2:
      arg1, arg2 = sys.argv   # script arguments
      if arg2 == "auto":
         runConsoleHandler(["start", "connect"])
   else:
         runConsoleHandler([])
   # ================================================================================
# endif


#=====================================================================================
