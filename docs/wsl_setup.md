## Setup with WSL 2

#### Enter Environment

Initial setup must already be done of course.
1. `wsl -d Ubuntu-22.04`
2. `cd`

#### Initial Setup
1. `wsl --set-default-version 2`
2. `wsl --update`
3. `wsl --install -d Ubuntu-22.04`
    * enter desired username/password
4. `curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install`
    * enter password
    * accept default settings
5. `. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh`
6. `git clone` the repository
7. `nix profile install nixpkgs#zstd`

#### USB Setup
todo...
