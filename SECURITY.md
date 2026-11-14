🇺🇸 English · [🇧🇷 Português](SECURITY.pt-BR.md)

# Security policy

Deproi runs as root on your server, triggered from GitHub. Security reports are taken seriously and handled first.

## Reporting a vulnerability

**Do not open a public issue.** Use GitHub's private reporting: [Report a vulnerability](https://github.com/rodrigo-pasini/deproi/security/advisories/new).

Please include the Deproi version, what an attacker needs (push access? the deploy key? a shell on the server?), what they gain, and steps to reproduce. You can expect a first answer within 7 days. Fixes are released as a new version with a GitHub Security Advisory, and you are credited unless you ask otherwise.

## Supported versions

| Version | Supported |
|---|---|
| Latest minor release | ✅ |
| Older releases | ❌ upgrade first |

## Security model in short

- Anyone who can push to a deploy branch can run code as root on that server, because Docker Compose runs the project's containers. Protect deploy branches accordingly.
- The SSH deploy key can only trigger the deploy (`restrict,command=`); it cannot open a shell or pass arguments.
- The deploy script and its config live outside the checkout, owned by root.

In scope: anything that lets someone go beyond that model, for example running arbitrary commands with the deploy key, choosing another target, or reading server secrets through the deploy output.
