Scheduler Plugins
=================

**This page is unfortunately under construction. If you're interested in
writing your own scheduler plugins, let us know and we'll make fixing this a
top priority.**

Scheduler plugins take care of the scheduling part of testing. For this
documentation, we will use the ``raw`` scheduler plugin for examples.

Writing Scheduler Plugins
-------------------------

Scheduler plugins require the `source code <#writing-the-source>`__ and
the `.yapsy-plugin file <basics.html#yapsy-plugin>`__.

Writing the Source
~~~~~~~~~~~~~~~~~~

At the very least, each scheduler plugin will have a `variable
class <#the-variables-class>`__ and the actual

The Variables Class
^^^^^^^^^^^^^^^^^^^

Every scheduler plugin module has to have a variables class that is a
child of the ``SchedulerVariables`` class found in ``schedulers.py``.

.. code:: python

    class RawVars(SchedulerVariables):

To add a variable, add a method with the same name as the variable and
decorate it with either ``@sched_var`` or ``dfr_sched_var`` (for
deferred variables).

For example, the ``raw`` scheduler has a variable called ``cpus``. The
method for this variable is as follows:

.. code:: python

    @var_method
    def cpus(self):
        """Total CPUs (includes hyperthreading cpus)."""
        return self.sched_data['cpus']

