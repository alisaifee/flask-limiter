.. :changelog:

Changelog
=========

0.4 2014-05-28
--------------
* `Rate limiting headers
  <http://flask-limiter.readthedocs.org/en/latest/#rate-limiting-headers>`_

0.3.2 2014-05-26
----------------
* Bug fix 

  * Memory leak when using ``Limiter.storage.MemoryStorage`` 
    (`Issue 4 <https://github.com/alisaifee/flask-limiter/issues/4>`_.)
* Improved test coverage 

0.3.1 2014-02-20
----------------
* Strict version requirement on six
* documentation tweaks 

0.3.0 2014-02-19
----------------
* improved logging support for multiple handlers 
* allow callables to be passed to ``Limiter.limit`` decorator to dynamically
  load rate limit strings.
* add a global kill switch in flask config for all rate limits.
* Bug fixes 

  * default key function for rate limit domain wasn't accounting for 
    X-Forwarded-For header.



0.2.2 2014-02-18
----------------
* add new decorator to exempt routes from limiting.
* Bug fixes 
    
  * versioneer.py wasn't included in manifest. 
  * configuration string for strategy was out of sync with docs.

0.2.1 2014-02-15
----------------
* python 2.6 support via counter backport
* source docs.

0.2 2014-02-15
--------------
* Implemented configurable strategies for rate limiting.
* Bug fixes 
  
  * better locking for in-memory storage 
  * multi threading support for memcached storage 


0.1.1 2014-02-14
----------------
* Bug fixes

  * fix initializing the extension without an app
  * don't rate limit static files 


0.1.0 2014-02-13
----------------
* first release.









