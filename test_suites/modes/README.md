# modes

This directory contains the files that allow for modifying the mode in which
the tests should be run.  The different modes that can be modified include
the account, partition, QOS, and reservation under which the test will be run.

The available modes include:
- acct-hpcdev: Runs using the hpcdev account.
- acct-hpctest: Runs using the hpctest account.
- part-haswell: Runs on the Haswell partition (Trinity or Trinitite).
- part-knl: Runs on the Knights Landing partition (Trinity or Trinitite).
- part-tossdev: Runs on the tossdev partition.
- qos-large: Runs using the large quality of service.
- qos-long: Runs using the long quality of service.
- qos-standard: Runs using the standard quality of service.
- qos-standby: Runs using the standby quality of service.
- qos-yield: Runs using the yield quality of service.
- res-PreventMaint: Runs in the PreventMaint reservation.
