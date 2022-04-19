Command Line Interface
======================

.. versionadded:: 2.4.0

Flask-Limiter adds a few subcommands to the Flask :doc:`flask:cli` for maintenance & diagnostic purposes.
These can be accessed under the **limiter** sub-command as follows

.. program-output:: FLASK_APP=../../examples/kitchensink.py:app flask limiter --help
   :shell:

Example
-------

The examples below use the following example application:

.. literalinclude:: ../../examples/kitchensink.py
   :language: py

Extension Config
^^^^^^^^^^^^^^^^
Use the subcommand **config** to display the active configuration

.. code-block:: shell

  $ flask limiter config

.. command-output:: FLASK_APP=../../examples/kitchensink.py:app flask limiter config
   :shell:

List limits
^^^^^^^^^^^
.. code-block:: shell

  $ flask limiter limits

Use the subcommand **limits** to display all configured limits

.. command-output:: FLASK_APP=../../examples/kitchensink.py:app flask limiter limits
   :shell:

=======================
Filter by endpoint name
=======================

.. command-output:: FLASK_APP=../../examples/kitchensink.py:app flask limiter limits --endpoint=root
   :shell:

==============
Filter by path
==============

.. command-output:: FLASK_APP=../../examples/kitchensink.py:app flask limiter limits --path=/health/
   :shell:

==================
Check limit status
==================

.. command-output:: FLASK_APP=../../examples/kitchensink.py:app flask limiter limits --key=127.0.0.1
   :shell:

Clear limits
^^^^^^^^^^^^
.. code-block:: shell

  $ flask limiter clear

The CLI exposes a subcommand **clear** that can be used to clear either all limits or limits for specific endpoints or routes by a
``key`` which represents the value returned by the :paramref:`~flask_limiter.Limiter.key_func` (i.e. a specific user)
callable configured for your application.

.. command-output:: FLASK_APP=../../examples/kitchensink.py:app flask limiter clear --help
   :shell:

By default this is an interactive command which requires confirmation, however it can
also be used in automations by using the ``-y`` flag to force confirmation.

.. command-output:: FLASK_APP=../../examples/kitchensink.py:app flask limiter clear --key=127.0.0.1 -y
   :shell:


