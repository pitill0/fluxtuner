# Web metadata network security

## Scope

Phase 6 adds dynamic `Now Playing` metadata to FluxTuner Web. The backend will
need to inspect remote radio streams because browsers must not connect to
arbitrary streams for metadata discovery.

This document defines the security boundary before any network client is added.
The first Phase 6 pull request contains contracts and tests only: it performs no
DNS resolution, socket connection or HTTP request.

## Threat model

An authenticated Web user can cause FluxTuner to consider a stream URL supplied
by station data or by a future metadata endpoint. Authentication and CSRF
protection do not make that URL trustworthy. A malicious or compromised user
could try to use the server as an SSRF proxy to reach services that are not
otherwise exposed.

The protected assets include:

- loopback services on the FluxTuner host;
- private and link-local networks reachable from the host;
- cloud or hosting metadata services;
- internal DNS names and addresses;
- Unix-adjacent or non-HTTP resources exposed through unusual URL schemes;
- server availability, file descriptors, memory and outbound bandwidth;
- remote radio stations that must not be flooded by repeated metadata probes.

## Mandatory destination policy

Every future metadata fetch must enforce all of these rules:

1. Accept only `http` and `https` URLs.
2. Reject credentials, fragments, control characters, malformed hosts, invalid
   ports, ambiguous IP spellings and IPv6 zone identifiers.
3. Normalize the URL conservatively before deriving a cache key or resolving it.
4. Resolve the hostname through an injectable resolver boundary.
5. Classify every returned IPv4 and IPv6 address.
6. Permit a destination only when every candidate address is globally routable.
7. Block loopback, private, shared carrier-grade NAT, link-local, multicast,
   unspecified and reserved destinations, including blocked IPv4 addresses
   represented through IPv6.
8. Connect to an address that was actually validated while preserving the
   original hostname for HTTP `Host` handling and TLS SNI.
9. Do not validate DNS and then hand the untouched hostname to a client that may
   resolve it again independently.
10. Re-run the complete URL and destination policy for every redirect.
11. Reject HTTPS-to-HTTP redirects by default.
12. Send no authentication cookie, CSRF token or other FluxTuner credential to a
    remote stream.

The later implementation must explicitly cover DNS rebinding. Merely checking
resolved addresses before a conventional hostname-based request is not enough.

## Resource limits

The initial contract sets conservative upper bounds:

| Limit | Value |
|---|---:|
| URL length | 2048 characters |
| Redirects | 3 |
| Connect timeout | 2 seconds |
| Read timeout | 2 seconds |
| Total fetch budget | 5 seconds |
| Response headers | 32 KiB |
| ICY metadata interval | 1 MiB |
| ICY metadata block | 4080 bytes |

A future client may use stricter limits, but it must not silently exceed these
values without a dedicated review.

## Lifecycle and isolation requirements

The metadata subsystem must remain separate from playback success. A metadata
failure must never turn a playable station into a playback error.

Future work must also provide:

- one shared cache per process rather than one cache per user;
- bounded global concurrency and a bounded work queue;
- deduplication by normalized stream URL;
- conservative TTLs and exponential backoff;
- no worker per user or browser tab;
- endpoint responses that do not wait for remote network completion;
- tests based on fake resolvers and transports, never live radio stations;
- logs and metrics that avoid exposing full stream URLs or unbounded labels.

## Out of scope for this contract pull request

This pull request does not implement sockets, HTTP, ICY fetching, caching,
workers, FastAPI endpoints or browser polling. URL normalization, DNS resolution
and address classification are implemented here and remain independently
testable without opening network connections.

## Protected transport

The protected transport connects to one exact address returned by the validated
resolution policy. For HTTPS, TLS SNI continues to use the normalized hostname;
HTTP `Host` also preserves that hostname. The transport never hands the hostname
back to a conventional client for a second DNS lookup.

Each request:

- sends no FluxTuner cookies, authorization headers or CSRF data;
- requests ICY metadata explicitly;
- applies the configured connect, read and total time budgets;
- bounds response headers before parsing them;
- accepts HTTP/1.0, HTTP/1.1 and legacy `ICY` status lines;
- reads only the first bounded ICY metadata block;
- closes the remote stream after that block;
- re-normalizes and re-resolves every redirect target;
- rejects HTTPS-to-HTTP redirects by default;
- enforces the configured redirect limit.

This layer remains synchronous and contains no cache, worker or FastAPI
lifecycle. Later work will execute it behind a bounded background coordinator.

## Process-wide coordinator

The metadata coordinator owns one bounded cache per server process. Callers ask
for a normalized stream URL and receive an immutable snapshot immediately;
remote network work is submitted separately and never runs on the request path.

The coordinator:

- deduplicates work by normalized stream URL;
- permits at most one in-flight refresh per URL;
- caps the total submitted/running work count;
- uses a fixed-size thread pool rather than one worker per user or browser tab;
- applies separate TTLs to metadata and empty results;
- applies bounded exponential backoff after failures;
- retains the last successful value while a refresh is pending;
- bounds cache entry count and evicts the least recently touched idle entry;
- exposes no raw exception text or remote URL in normal logs;
- supports explicit process shutdown.

This pull request does not expose an HTTP endpoint or connect the coordinator to
the FastAPI lifespan. Those integrations remain separate so lifecycle ownership
can be reviewed independently.

## FastAPI lifecycle and cached endpoint

The FastAPI application owns exactly one metadata coordinator instance through
its lifespan. Startup creates the coordinator and stores it in application
state. Shutdown closes the coordinator and removes the state reference.

`GET /api/metadata?url=...`:

- requires an authenticated FluxTuner Web session;
- validates the supplied URL through the metadata subsystem;
- returns the current immutable cache snapshot immediately;
- may schedule a bounded background refresh;
- never waits for DNS, TCP, TLS, redirects or ICY reads;
- exposes no raw transport exception text;
- returns only normalized URL, cache status, metadata and failure count.

Absolute monotonic timestamps remain internal. They are not serialized because
their values have meaning only inside the running server process.

