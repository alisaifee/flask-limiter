.. :changelog:

Changelog
=========

v3.7.0
------
Release Date: 2024-05-19

* Bug fix

  * Fix errors with concurrent access to internal exemption maps
    during application startup.

v3.6.0
------
Release Date: 2024-04-21

* Bug fix

  * Ensure `exempt` routes are exempt from meta limits as well


v3.5.1
------
Release Date: 2024-02-11

* Chores

  * Update development dependencies
  * Use ruff for all linting
  * Update CI compatibility matrix

v3.5.0
------
Release Date: 2023-08-30

* Feature

  * Add `meta_limits` to allow for creating upper limits for
    requesting clients to breach application rate limits.

* Bug fix

  * Ensure on breach callbacks can be configured using flask config

v3.4.1
------
Release Date: 2023-08-26

* Bug fix

  - Ensure _version.py has stable content when generated
    using `git archive` from a tag regardless of when it is
    run.

v3.4.0
------
Release Date: 2023-08-22

* Feature

  * Add extended configuration for application limits

    * `application_limits_exempt_when`
    * `application_limits_deduct_when`
    * `application_limits_per_method`

* Bug fix

  * Ensure blueprint static routes are exempt

v3.3.1
------
Release Date: 2023-05-03

* Chores

  * Improve default limits documentation
  * Update documentation dependencies
  * Fix typing compatibility errors in headers

v3.3.0
------
Release Date: 2023-02-26

* Bug Fix

  * Ensure per route limits are preferred (over application limits)
    when populating rate limiting headers in the case where no rate limit has been
    breached in the request.

v3.2.0
------
Release Date: 2023-02-15

* Feature

  * Allow configuring request identity

* Chores

  * Improve linting with ruff
  * Update development dependencies


v3.1.0
------
Release Date: 2022-12-29

* Feature

  * Skip logging an error if a decorated limit uses a callable
    to return the "current" rate limit and returns an empty string.
    Treat this is a signal that the rate limit should be skipped for
    this request.

v3.0.0
------
Release Date: 2022-12-28

* Breaking changes

  * Change order of extension constructor arguments to only require
    ``key_func`` as the first positional argument and all other arguments
    as keyword arguments.
  * Separate positional/keyword arguments in limit/shared_limit decorators
  * Remove deprecated config variable RATELIMIT_STORAGE_URL
  * Remove legacy backward compatibility path for flask < 2

* Features

  * Allow scoping regular limit decorators / context managers

v3.0.0b2
--------
Release Date: 2022-12-28

* Breaking changes

  * Remove deprecated config variable RATELIMIT_STORAGE_URL
  * Remove legacy backward compatibility path for flask < 2
  * Enforce key_func as a required argument

* Chores

  * Simplify registration of decorated function & blueprint limits

v3.0.0b1
--------
Release Date: 2022-12-26

* Breaking changes

  * Change order of extension constructor arguments to only require
    ``key_func`` as the first positional argument and all other arguments
    as keyword arguments.
  * Separate positional/keyword arguments in limit/shared_limit decorators

* Features

  * Allow scoping regular limit decorators / context managers

v2.9.2
------
Release Date: 2022-12-26

* Feature

  * Extend customization by http method to shared_limit decorator

v2.9.1
------
Release Date: 2022-12-26

* Chores

  * Update documentation quick start
  * Refresh documentation for class based views

v2.9.0
------
Release Date: 2022-12-24

* Features

  * Allow using `limit` & `shared_limit` decorators on pure
    functions that are not decorated as routes. The functions
    when called from within a request context will get rate limited.
  * Allow using `limit` as a context manager to rate limit a code block
    explicitly within a request

* Chores

  * Updated development dependencies
  * Fix error running tests depending on docker locally
  * Update internals to use dataclasses

v2.8.1
------
Release Date: 2022-11-15

* Chores

  * Add sponsorship banner to rtd
  * Update documentation dependencies

v2.8.0
------
Release Date: 2022-11-13

* Breaking changes

  * Any exception raised when calling an ``on_breach`` callback will
    be re-raised instead of being absorbed unless ``swallow_errors`` is set.
    In the case of ``swallow_errors`` the exception will now be logged
    at ``ERROR`` level instead of ``WARN``
  * Reduce log level of rate limit exceeded log messages to ``INFO``

v2.7.0
------
Release Date: 2022-10-25

* Bug Fix

  * Add default value for RateLimitExceeded optional parameter
  * Fix suppression of errors when using conditional deduction (`Issue 363 <https://github.com/alisaifee/flask-limiter/issues/363>`_)

v2.6.3
------
Release Date: 2022-09-22

* Compatibility

  * Ensure typing_extensions dependency has a minimum version

* Chores

  * Documentation tweaks
  * Update CI to use 3.11 rc2

v2.6.2
------
Release Date: 2022-08-24

* Chores

  * Improve quick start documentation

v2.6.1
------
Release Date: 2022-08-23

* Usability

  * Emit warning when in memory storage is used as a default
    when no storage uri is provided

v2.6.0
------
Release Date: 2022-08-11

* Feature

  * Expand use of ``on_breach`` callback to return a ``Response``
    object that will be used as the error response on rate limits
    being exceeded


v2.5.1
------
Release Date: 2022-08-05

* Compatibility

  * Migrate use of `flask._request_ctx_stack` to `flask.globals.request_ctx`
    to support Flask 2.2+

* Chores

  * Expand CI matrix to test against Flask 2.0,2.1 & 2.2
  * Make tests compatible with Flask 2.2.+

v2.5.0
------
Release Date: 2022-07-07

* Features

  * Ensure multiple extension instances registered
    on a single application exercise before/after request
    hooks

* Chores

  * Improve documentation

v2.4.6
------
Release Date: 2022-06-06

* Chore

  * Add python 3.11 to CI matrix


v2.4.5.1
--------
Release Date: 2022-04-22

* Chore

  * Automate github releases

v2.4.5
------
Release Date: 2022-04-21

* Chore

  * Automate github releases

v2.4.4
------
Release Date: 2022-04-21

* Chore

  * Automate github releases

v2.4.3
------
Release Date: 2022-04-21

* Chore

  * Second attempt to generate release notes

v2.4.2
------
Release Date: 2022-04-21

* Chore

  * Test for automating github release notes

v2.4.1
------
Release Date: 2022-04-21

* Chore

  * Automate github releases

v2.4.0
------
Release Date: 2022-04-20

* Feature

  * Add CLI for inspecting & clearing rate limits

* Bug Fix

  * Ensure exempt decorator can be used with flags for view functions

* Chores

  * Refactor rate limit resolution to limit manager

v2.3.3
------
Release Date: 2022-04-20

* Bug Fix

  * Ensure `request.blueprint` is actually registered on the current app before
    using it for blueprint limits or exemptions. (`Issue 336 <https://github.com/alisaifee/flask-limiter/issues/336>`_)

v2.3.2
------
Release Date: 2022-04-17

* Feature

  * Extend cost parameter to default & application limits

* Chore

  * Improve type strictness / checking
  * Improve documentation on landing page

v2.3.1
------
Release Date: 2022-04-14

* Bug Fixes

  * Add missing extras requirements for installation
  * Add py.typed for PEP 561 compliance

v2.3.0
------
Release Date: 2022-04-11

* Features

  * Expose option to register a callback for rate limit breaches
    of default limits via the :paramref:`~flask_limiter.Limiter.on_breach`
    constructor parameter
  * Replace use of `flask.g` with request context for keeping track of
    extension state (:issue:`327`)
  * Rework implementation of :meth:`~flask_limiter.Limiter.exempt` to accomodate
    nested blueprints. (:issue:`326`)

* Chores

  * Add python 3.11 to CI
  * Extract management and filtering of limits to LimitManager
  * Improve correctness of resolving inherited limits & extensions
    when working with Blueprints (especially nested ones)


v2.2.0
------
Release Date: 2022-03-05

* Feature

  * Allow a function to be used for the ``cost`` parameter
    to limiter decorators.

v2.1.3
------
Release Date: 2022-01-30

* Chore

  * Update documentation theme

v2.1
----
Release Date: 2022-01-15

* Feature

  * Add ``current_limit`` attribute to extension to
    allow clients to fetch the relevant current limit
    that was evaluated.
  * Update extension constructor parameters to match
    flask config for header control
  * Add ``on_breach`` callback for ``limit`` and ``shared_limit``
    decorators to be used as hooks for when a limit is breached
  * Add ``cost`` argument to ``limit`` and ``shared_limit`` to control
    how much is deducted when a hit occurs.

* Chore

  * Improve documentation around configuration

* Deprecation

  * Remove hacks for managing incorrectly ordered
    limit/route decorators

v2.0.4
------
Release Date: 2021-12-22

* Chore

  * Documentation theme upgrades
  * Integrate pytest-docker plugin
  * Mass linting

* Deprecation

  * Removed deprecated RATELIMIT_GLOBAL config
  * Added deprecation doc for RATELIMIT_STORAGE_URL config

v2.0.3
------
Release Date: 2021-12-15

Documentation & test tweaks

v2.0.2
------
Release Date: 2021-11-28

* Features

  * Pin Flask, limits to >= 2
  * Add type hints

v2.0.1
------
Release Date: 2021-11-28

* Deprecations

  * Remove deprecated get_ipaddr method
  * Remove use of six
  * Remove backward compatibility hacks for RateLimit exceptions

v2.0.0
------
Release Date: 2021-11-27

Drop support for python < 3.7 & Flask < 2.0

v1.5
----
Release Date: 2021-11-27

Final Release for python < 3.7

* Features

  * Prepend ``key_prefix`` to extension variables attached to ``g``
  * Expose ``g.view_limits``

v1.4
----
Release Date: 2020-08-25

* Bug Fix

  * Always set headers for conditional limits
  * Skip init_app sequence when the rate limiter is disabled

v1.3.1
------
Release Date: 2020-05-21

* Bug Fix

  * Ensure headers provided explictely by setting `_header_mapping`
    take precedence over configuration values.

v1.3
----
Release Date: 2020-05-20

* Features

  * Add new ``deduct_when`` argument that accepts a function to decorated limits
    to conditionally perform depletion of a rate limit (`Pull Request 248 <https://github.com/alisaifee/flask-limiter/pull/248>`_)
  * Add new ``default_limits_deduct_when`` argument to Limiter constructor to
    conditionally perform depletion of default rate limits
  * Add ``default_limits_exempt_when`` argument that accepts a function to
    allow skipping the default limits in the ``before_request`` phase

* Bug Fix

  * Fix handling of storage failures during ``after_request`` phase.

* Code Quality

  * Use github-actions instead of travis for CI
  * Use pytest instaad of nosetests
  * Add docker configuration for test dependencies
  * Increase code coverage to 100%
  * Ensure pyflake8 compliance


v1.2.1
------
Release Date: 2020-02-26

* Bug fix

  * Syntax error in version 1.2.0 when application limits are provided through
    configuration file (`Issue 241 <https://github.com/alisaifee/flask-limiter/issues/241>`_)

v1.2.0
------
Release Date: 2020-02-25

* Add `override_defaults` argument to decorated limits to allow combinined defaults with decorated limits.
* Add configuration parameter RATELIMIT_DEFAULTS_PER_METHOD to control whether defaults are applied per method.
* Add support for in memory fallback without override (`Pull Request 236 <https://github.com/alisaifee/flask-limiter/pull/236>`_)
* Bug fix

  * Ensure defaults are enforced when decorated limits are skipped (`Issue 238 <https://github.com/alisaifee/flask-limiter/issues/238>`_)

v1.1.0
------
Release Date: 2019-10-02

* Provide Rate limit information with Exception (`Pull Request 202 <https://github.com/alisaifee/flask-limiter/pull/202>`_)
* Respect existing Retry-After header values (`Pull Request 143 <https://github.com/alisaifee/flask-limiter/pull/143>`_)
* Documentation improvements

v1.0.1
------
Release Date: 2017-12-08

* Bug fix

  * Duplicate rate limits applied via application limits (`Issue 108 <https://github.com/alisaifee/flask-limiter/issues/108>`_)

v1.0.0
------
Release Date: 2017-11-06

* Improved documentation for handling ip addresses for applications behind proxiues (`Issue 41 <https://github.com/alisaifee/flask-limiter/issues/41>`_)
* Execute rate limits for decorated routes in decorator instead of `before_request`  (`Issue 67 <https://github.com/alisaifee/flask-limiter/issues/67>`_)
* Bug Fix

  * Python 3.5 Errors (`Issue 82 <https://github.com/alisaifee/flask-limiter/issues/82>`_)
  * RATELIMIT_KEY_PREFIX configuration constant not used (`Issue 88 <https://github.com/alisaifee/flask-limiter/issues/88>`_)
  * Can't use dynamic limit in `default_limits` (`Issue 94 <https://github.com/alisaifee/flask-limiter/issues/94>`_)
  * Retry-After header always zero when using key prefix (`Issue 99 <https://github.com/alisaifee/flask-limiter/issues/99>`_)

v0.9.5.1
--------
Release Date: 2017-08-18

* Upgrade versioneer

v0.9.5
------
Release Date: 2017-07-26

* Add support for key prefixes

v0.9.4
------
Release Date: 2017-05-01

* Implemented application wide shared limits

v0.9.3
------
Release Date: 2016-03-14

* Allow `reset` of limiter storage if available

v0.9.2
------
Release Date: 2016-03-04

* Deprecation warning for default `key_func` `get_ipaddr`
* Support for `Retry-After` header

v0.9.1
------
Release Date: 2015-11-21

* Re-expose `enabled` property on `Limiter` instance.

v0.9
-----
Release Date: 2015-11-13

* In-memory fallback option for unresponsive storage
* Rate limit exemption option per limit

v0.8.5
------
Release Date: 2015-10-05

* Bug fix for reported issues of missing (limits) dependency upon installation.

v0.8.4
------
Release Date: 2015-10-03

* Documentation tweaks.

v0.8.2
------
Release Date: 2015-09-17

* Remove outdated files from egg

v0.8.1
------
Release Date: 2015-08-06

* Fixed compatibility with latest version of **Flask-Restful**

v0.8
-----
Release Date: 2015-06-07

* No functional change

v0.7.9
------
Release Date: 2015-04-02

* Bug fix for case sensitive `methods` whitelist for `limits` decorator

v0.7.8
------
Release Date: 2015-03-20

* Hotfix for dynamic limits with blueprints
* Undocumented feature to pass storage options to underlying storage backend.

v0.7.6
------
Release Date: 2015-03-02

* `methods` keyword argument for `limits` decorator to specify specific http
  methods to apply the rate limit to.

v0.7.5
------
Release Date: 2015-02-16

* `Custom error messages <http://flask-limiter.readthedocs.org/en/stable/#custom-error-messages>`_.

v0.7.4
------
Release Date: 2015-02-03

* Use Werkzeug TooManyRequests as the exception raised when available.

v0.7.3
------
Release Date: 2015-01-30

* Bug Fix

  * Fix for version comparison when monkey patching Werkzeug
        (`Issue 24 <https://github.com/alisaifee/flask-limiter/issues/24>`_)

v0.7.1
------
Release Date: 2015-01-09

* Refactor core storage & ratelimiting strategy out into the `limits <http://github.com/alisaifee/limits>`_ package.
* Remove duplicate hits when stacked rate limits are in use and a rate limit is hit.

v0.7
----
Release Date: 2015-01-09

* Refactoring of RedisStorage for extensibility (`Issue 18 <https://github.com/alisaifee/flask-limiter/issues/18>`_)
* Bug fix: Correct default setting for enabling rate limit headers. (`Issue 22 <https://github.com/alisaifee/flask-limiter/issues/22>`_)

v0.6.6
------
Release Date: 2014-10-21

* Bug fix

  * Fix for responses slower than rate limiting window.
    (`Issue 17 <https://github.com/alisaifee/flask-limiter/issues/17>`_.)

v0.6.5
------
Release Date: 2014-10-01

* Bug fix: in memory storage thread safety

v0.6.4
------
Release Date: 2014-08-31

* Support for manually triggering rate limit check

v0.6.3
------
Release Date: 2014-08-26

* Header name overrides

v0.6.2
------
Release Date: 2014-07-13

* `Rate limiting for blueprints
  <http://flask-limiter.readthedocs.org/en/latest/#rate-limiting-all-routes-in-a-flask-blueprint>`_

v0.6.1
------
Release Date: 2014-07-11

* per http method rate limit separation (`Recipe
  <http://flask-limiter.readthedocs.org/en/latest/index.html#using-flask-pluggable-views>`_)
* documentation improvements

v0.6
----
Release Date: 2014-06-24

* `Shared limits between routes
  <http://flask-limiter.readthedocs.org/en/latest/index.html#ratelimit-decorator-shared-limit>`_

v0.5
----
Release Date: 2014-06-13

* `Request Filters
  <http://flask-limiter.readthedocs.org/en/latest/index.html#ratelimit-decorator-request-filter>`_

v0.4.4
------
Release Date: 2014-06-13

* Bug fix

  * Werkzeug < 0.9 Compatibility
    (`Issue 6 <https://github.com/alisaifee/flask-limiter/issues/6>`_.)

v0.4.3
------
Release Date: 2014-06-12

* Hotfix : use HTTPException instead of abort to play well with other
  extensions.

v0.4.2
------
Release Date: 2014-06-12

* Allow configuration overrides via extension constructor

v0.4.1
------
Release Date: 2014-06-04

* Improved implementation of moving-window X-RateLimit-Reset value.

v0.4
----
Release Date: 2014-05-28

* `Rate limiting headers
  <http://flask-limiter.readthedocs.org/en/latest/#rate-limiting-headers>`_

v0.3.2
------
Release Date: 2014-05-26

* Bug fix

  * Memory leak when using ``Limiter.storage.MemoryStorage``
    (`Issue 4 <https://github.com/alisaifee/flask-limiter/issues/4>`_.)
* Improved test coverage

v0.3.1
------
Release Date: 2014-02-20

* Strict version requirement on six
* documentation tweaks

v0.3.0
------
Release Date: 2014-02-19

* improved logging support for multiple handlers
* allow callables to be passed to ``Limiter.limit`` decorator to dynamically
  load rate limit strings.
* add a global kill switch in flask config for all rate limits.
* Bug fixes

  * default key function for rate limit domain wasn't accounting for
    X-Forwarded-For header.

v0.2.2
------
Release Date: 2014-02-18

* add new decorator to exempt routes from limiting.
* Bug fixes

  * versioneer.py wasn't included in manifest.
  * configuration string for strategy was out of sync with docs.

v0.2.1
------
Release Date: 2014-02-15

* python 2.6 support via counter backport
* source docs.

v0.2
----
Release Date: 2014-02-15

* Implemented configurable strategies for rate limiting.
* Bug fixes

  * better locking for in-memory storage
  * multi threading support for memcached storage


v0.1.1
------
Release Date: 2014-02-14

* Bug fixes

  * fix initializing the extension without an app
  * don't rate limit static files


v0.1.0
------
Release Date: 2014-02-13

* first release.


































































































