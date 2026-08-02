# Deep-Dive Network Report — Lab (dual-router / dual-switch)

## Summary
Layer-3 core (eBGP + OSPF) is fully healthy with 100% end-to-end reachability.
Deep inspection uncovered a Layer-2 misconfiguration: the inter-switch LACP trunk
(Po1) carries NO active VLANs because VLANs 10 and 20 are trunk-allowed but were
never created in the VLAN database on either switch. As a result the Vlan10/Vlan20
SVIs are down and the two switches form independent (split-brain) spanning trees.
No current data-plane outage, but the switch-to-switch L2 redundancy is non-functional.

## Root Cause
VLANs 10 and 20 are missing from the VLAN database on both SW1 (192.168.0.12) and
SW2 (192.168.0.13). Po1 is configured to trunk only VLANs 10,20 and both switches
have SVIs Vlan10 (10.0.10.1) / Vlan20 (10.0.20.1) plus SW1 uses 10.0.10.1 as OSPF
RID — but because the VLANs do not exist, the trunk passes zero active VLANs, the
SVIs stay down/down, and no BPDUs cross Po1.

## Evidence
### Layer 3 (healthy)
- R1 `show ip bgp summary`: neighbor 10.255.0.2 (AS65002) Established, 1 pfx.
- R2 `show ip bgp summary`: neighbor 10.255.0.1 (AS65001) Established, 1 pfx.
- R1/R2 `show ip ospf neighbor`: all FULL. Switches FULL/BDR with both routers.
- R1 `show ip route`: B 2.2.2.2 via 10.255.0.2; O 10.0.0.8/30, 10.0.0.12/30.
- R2 `show ip route`: B 1.1.1.1 via 10.255.0.1; O 10.0.0.0/30, 10.0.0.4/30.
- R1 ping 2.2.2.2 src 1.1.1.1: 100% (5/5). R2 ping 1.1.1.1 src 2.2.2.2: 100%.

### Layer 2 (misconfigured)
- SW1/SW2 `show interfaces trunk`: Po1 trunking, allowed VLANs 10,20;
  "allowed and active: none"; "forwarding and not pruned: none".
- SW1/SW2 `show vlan brief`: only VLAN 1 present; VLANs 10 and 20 absent.
- SW1 `show ip interface brief`: Vlan10 (10.0.10.1) and Vlan20 (10.0.20.1) down/down.
- SW1/SW2 `show spanning-tree`: each switch reports "This bridge is the root" for
  VLAN1 (split-brain) because VLAN1 is not carried on Po1 and VLANs 10/20 are inactive.
- SW1/SW2 `show etherchannel summary`: Po1(SU), Gi0/2(P)+Gi0/3(P) bundled (L1/L2 fine).

## Impact
- No current outage: router/loopback traffic uses routed /30 links and the direct
  R1<->R2 link via OSPF/BGP, independent of the switch-to-switch path.
- Switch-to-switch L2 redundancy is non-functional: VLAN 10/20 host segments would be
  isolated between SW1 and SW2; gateways 10.0.10.1 / 10.0.20.1 are down.
- Fragility: SW1 OSPF Router-ID (10.0.10.1) references a down SVI.

## Fix Commands
Apply on BOTH switches (192.168.0.12 and 192.168.0.13):

    configure terminal
    vlan 10
     name DATA
    vlan 20
     name VOICE
    end
    write memory

After creation, VLANs 10/20 become active on Po1, the Vlan10/Vlan20 SVIs come up,
BPDUs traverse Po1, and a single STP root is elected for those VLANs.

### Verification after fix
    show vlan brief                       (VLAN 10, 20 present/active)
    show interfaces trunk                 (Po1 allowed AND active: 10,20)
    show ip interface brief | inc Vlan    (Vlan10/Vlan20 up/up)
    show spanning-tree vlan 10            (single root across SW1/SW2)
    show spanning-tree vlan 20

### Notes / options
- VLAN1 will still show two roots because VLAN1 is intentionally not trunked on Po1.
  This is harmless (only unused ports Gi1/1-3 are in VLAN1). If undesired, either add
  VLAN1 to the trunk or move unused ports out of VLAN1.
- Consider setting an explicit OSPF router-id on SW1 (e.g., a loopback) so the RID does
  not depend on an SVI that can go down.
