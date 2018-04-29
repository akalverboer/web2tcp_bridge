Change log
----------
2018-05-01: Initial release <br/>

2018-04-29:
- Implementing max length of receiving messages from socket server or from webclient. <br/>
  Messages are truncated if too large. Max length defined by config parameter.
- Bug fix of received messages from socket server. <br/>
  Error in handling messages if socket server sends messages too fast. <br/>
  This is the case if a draughts client sends a back request of one capture.
  The draughts engine confirms the request and immediately does the capture again. <br/>
  Problem is solved.

