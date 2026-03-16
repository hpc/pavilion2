==========
flufl.lock
==========

NFS-safe file locking with timeouts for POSIX and Windows.

The ``flufl.lock`` library provides an NFS-safe file-based locking algorithm
influenced by the GNU/Linux ``open(2)`` manpage, under the description of the
``O_EXCL`` option.

    [...] O_EXCL is broken on NFS file systems, programs which rely on it
    for performing locking tasks will contain a race condition.  The
    solution for performing atomic file locking using a lockfile is to
    create a unique file on the same fs (e.g., incorporating hostname and
    pid), use link(2) to make a link to the lockfile.  If link() returns
    0, the lock is successful.  Otherwise, use stat(2) on the unique file
    to check if its link count has increased to 2, in which case the lock
    is also successful.

The assumption made here is that there will be no *outside interference*,
e.g. no agent external to this code will ever ``link()`` to the specific lock
files used.

Lock objects support lock-breaking so that you can't wedge a process forever.
This is especially helpful in a web environment, but may not be appropriate
for all applications.

Locks have a *lifetime*, which is the maximum length of time the process
expects to retain the lock.  It is important to pick a good number here
because other processes will not break an existing lock until the expected
lifetime has expired.  Too long and other processes will hang; too short and
you'll end up trampling on existing process locks -- and possibly corrupting
data.  In a distributed (NFS) environment, you also need to make sure that
your clocks are properly synchronized.


Author
======

``flufl.lock`` is Copyright (C) 2007-2021 Barry Warsaw <barry@python.org>

Licensed under the terms of the Apache License Version 2.0.  See the LICENSE
file for details.


Project details
===============

 * Project home: https://gitlab.com/warsaw/flufl.lock
 * Report bugs at: https://gitlab.com/warsaw/flufl.lock/issues
 * Code hosting: https://gitlab.com/warsaw/flufl.lock.git
 * Documentation: https://flufllock.readthedocs.io/
