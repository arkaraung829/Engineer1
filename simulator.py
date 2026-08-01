# simulator.py
# Pretends to be a Cisco IOS device.
# Returns realistic show command output without needing real hardware.

# This is a dictionary — think of it like a lookup table:
# Key   = the show command
# Value = what the device would actually return

DEVICE_RESPONSES = {
    "show ip bgp summary": """
BGP router identifier 10.0.0.1, local AS number 65001
BGP table version is 42, main routing table version 42

Neighbor        V    AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.0.0.2        4 65002       0       0        0    0    0 never    Idle
10.0.0.3        4 65003     150     148       42    0    0 02:31:05       12
""",

    "show ip bgp neighbors 10.0.0.2": """
BGP neighbor is 10.0.0.2, remote AS 65002, external link
  BGP state = Idle
  Last reset 00:15:32, due to: BGP Notification sent
  Notification error code: Hold Time expired
  Connection is Not established
""",

    "show ip interface brief": """
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0     10.0.0.1        YES manual up                    up
GigabitEthernet0/1     10.0.1.1        YES manual up                    up
GigabitEthernet0/2     unassigned      YES unset  administratively down down
Loopback0              1.1.1.1         YES manual up                    up
""",

    "show interfaces gigabitethernet0/2": """
GigabitEthernet0/2 is administratively down, line protocol is down
  Hardware is iGbE, address is aabb.cc00.0200
  MTU 1500 bytes, BW 1000000 Kbit/sec
  Input queue: 0/75/0/0 (size/max/drops/flushes)
  Output queue: 0/40 (size/max)
""",

    "show ip route": """
Codes: C - connected, S - static, R - RIP, B - BGP
       O - OSPF, I - IGRP

Gateway of last resort is 10.0.0.2 to network 0.0.0.0

C     10.0.0.0/24 is directly connected, GigabitEthernet0/0
C     10.0.1.0/24 is directly connected, GigabitEthernet0/1
B     192.168.0.0/16 [20/0] via 10.0.0.3, 02:31:05
""",

    "show log": """
Syslog logging: enabled (0 messages dropped, 0 flushes, 0 overruns)

*Jul 31 14:02:11.123: %BGP-5-ADJCHANGE: neighbor 10.0.0.2 Down Hold Time expired
*Jul 31 14:02:11.124: %BGP-3-NOTIFICATION: sent to neighbor 10.0.0.2 4/0 (hold time expired)
*Jul 31 13:45:00.001: %LINK-5-CHANGED: Interface GigabitEthernet0/2, changed state to administratively down
*Jul 31 13:44:59.999: %LINEPROTO-5-UPDOWN: Line protocol on Interface GigabitEthernet0/2, changed state to down
""",

    "show version": """
Cisco IOS Software, Version 15.7(3)M, RELEASE SOFTWARE
Router uptime is 2 days, 4 hours, 31 minutes
cisco ISR4321/K9 (1RU) processor
4 Gigabit Ethernet interfaces
""",

    "ping 10.0.0.2": """
Type escape sequence to abort.
Sending 5, 100-byte ICMP Echos to 10.0.0.2, timeout is 2 seconds:
!!!!!
Success rate is 100 percent (5/5), round-trip min/avg/max = 1/2/4 ms
""",

    "ping 10.0.0.2 size 1500 df-bit": """
Type escape sequence to abort.
Sending 5, 1500-byte ICMP Echos to 10.0.0.2, timeout is 2 seconds:
.....
Success rate is 0 percent (0/5)
""",

    "show interfaces gigabitethernet0/0": """
GigabitEthernet0/0 is up, line protocol is up
  Hardware is iGbE, address is aabb.cc00.0100 (bia aabb.cc00.0100)
  Internet address is 10.0.0.1/24
  MTU 1500 bytes, BW 1000000 Kbit/sec, DLY 10 usec
  Input queue: 0/75/0/0 (size/max/drops/flushes); Total output drops: 0
  5 minute input rate 1000 bits/sec, 2 packets/sec
  5 minute output rate 1000 bits/sec, 2 packets/sec
     12345 packets input, 9876543 bytes
     12340 packets output, 9870000 bytes
""",

    "show processes cpu": """
CPU utilization for five seconds: 8%/2%; one minute: 6%; five minutes: 5%
 PID Runtime(ms)  Invoked   uSecs    5Sec   1Min   5Min TTY Process
   1        1234     5678     217   0.00%  0.00%  0.00%   0 Chunk Manager
   2        5678    12345     459   0.00%  0.00%  0.00%   0 Load Meter
 169       98765   234567     421   0.47%  0.31%  0.28%   0 BGP Router
""",

    "show running-config": """
Building configuration...

Current configuration : 1842 bytes
!
version 15.7
hostname core-router-01
!
interface GigabitEthernet0/0
 ip address 10.0.0.1 255.255.255.0
 mtu 1500
 no shutdown
!
interface GigabitEthernet0/1
 ip address 10.0.1.1 255.255.255.0
 no shutdown
!
interface GigabitEthernet0/2
 no ip address
 shutdown
!
router bgp 65001
 bgp router-id 10.0.0.1
 neighbor 10.0.0.2 remote-as 65002
 neighbor 10.0.0.2 timers 60 180
 neighbor 10.0.0.3 remote-as 65003
 neighbor 10.0.0.3 timers 60 180
!
end
""",
}


def get_response(command: str) -> str:
    """
    Look up a command and return the fake device response.
    If the command is not in our dictionary, return an error message.
    """
    # Clean up the command (remove extra spaces, make lowercase for matching)
    command_clean = command.strip().lower()

    # Check each key in our dictionary
    for key in DEVICE_RESPONSES:
        if key in command_clean:
            return DEVICE_RESPONSES[key]

    # Command not found in our simulator
    return f"% Unrecognized command: {command}\n(Add it to simulator.py to support it)"
