Change log
----------
2018-05-01: Initial release
2018-04-29:
- Implementing fixed length of receiving messages from socket server or from webclient.
  Messages are truncated if too large. Max length defined by config parameter.
- Bug fix of received messages from socket server.
  Error in handling messages if socket server sends messages too fast.
  This is the case if a draughts client sends a back request of one capture.
  The draughts engine confirms the request and immediately does the capture again.
  Problem is solved.

