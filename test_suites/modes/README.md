# modes

This directory contains the files that allow for modifying the mode in which
the tests should be run.  The different modes that can be modified include
the account, partition, QOS, and reservation under which the test will be run.

The available modes include:
- [Accounts](https://hpc.lanl.gov/scheduling_policies#request_qos)
 - acct-hpcdev: Runs using the hpcdev account.
 - acct-hpctest: Runs using the hpctest account.
- [Partition](https://hpc.lanl.gov/trinitite_home#compute_nodes)
 - part-haswell: Runs on the Haswell partition (Trinity or Trinitite).
 - part-knl: Runs on the Knights Landing partition (Trinity or Trinitite).
 - part-tossdev: Runs on the tossdev partition.
- [QOS](https://hpc.lanl.gov/scheduling_policies#qos)
 - qos-large: Runs using the large quality of service.
 - qos-long: Runs using the long quality of service.
 - qos-standard: Runs using the standard quality of service.
 - qos-standby: Runs using the standby quality of service.
 - qos-yield: Runs using the yield quality of service.
- Reservation
 - res-PreventMaint: Runs in the PreventMaint reservation.
