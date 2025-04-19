{ inputs, ... }:
let
  cfg =
    {
      pkgs,
      lib,
      config,
      ...
    }:
    {
      users.mutableUsers = false;
      users.users.ahmed = {
        shell = pkgs.fish;
        isNormalUser = true;
        hashedPassword = "$6$rounds=150000$o.nB9z9eurlr7AIH$0hYwBY7KTfkpx59nURA02jE6AwSsVuJKG.4J0O4OiKz0K1hK2OpxKKtN9GIC1q1hMKvUvbEcrIplPnNRVPyXM0";
        openssh.authorizedKeys.keys = [
          "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMWmIZotZKBjPxKInXRjk9aVZtrpwxYbyawWHoNOKlaN name_snrl@t440s"
          "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJDEMlVpWlFe+Ogt5P3NAyMqG1KSpQjDBjJyEwRSsbmy satoko@WIN-MK011E50K5Q"
          "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIByll9gsPtixLrZBC4g8g9FB5lgMJjbSKuqrDjRgL6Sp saprilonty@mikhail-20s0003qus"
        ];
        extraGroups = [
          "wheel"
          "podman"
        ];
      };

      documentation.man.generateCaches = false;

      nixpkgs.config.allowUnfree = true;

      nix = {
        channel.enable = false;
        settings = {
          auto-optimise-store = true;
          use-xdg-base-directories = true;
          builders-use-substitutes = true;
          flake-registry = null;
          experimental-features = [
            "nix-command"
            "flakes"
          ];
          trusted-users = [
            "root"
            "@wheel"
          ];
        };
      };

      services = {
        vscode-server.enable = true;
        fail2ban.enable = true;
        openssh = {
          enable = true;
          ports = lib.singleton 22;
          settings = {
            PermitRootLogin = "no";
            AllowUsers = lib.singleton "ahmed";
            PasswordAuthentication = false;
            KbdInteractiveAuthentication = false;
          };
        };
      };

      virtualisation.podman = {
        enable = true;
        defaultNetwork.settings.dns_enabled = true;
        autoPrune = {
          enable = true;
          flags = [ "--all" ];
          dates = "0/3:*";
        };
      };

      systemd.user =
        let
          dirName = "mts_hackathon";
        in
        {
          # TODO it's a nonrecursive solution :(
          #
          # there is a better solution (podman compose doesn't support it), but I
          # don't have time for that:
          #
          # https://github.com/compose-spec/compose-spec/blob/main/develop.md
          paths.auto-deploy = {
            wantedBy = [ "default.target" ];
            pathConfig.PathChanged = "%h/${dirName}";
            pathConfig.TriggerLimitIntervalSec = "5s";
          };

          services.auto-deploy = {
            path = [
              config.virtualisation.podman.package
              pkgs.docker-compose
            ];
            script = ''
              set +e
              podman compose -f ~/${dirName}/docker-compose.yaml up -d --build --remove-orphans || true
            '';
            serviceConfig.Type = "oneshot";
            serviceConfig.Restart = "no";
          };
        };

      environment = {
        sessionVariables = {
          LESS = "FRSMi";
          SYSTEMD_LESS = "FRSMi";
        };
        systemPackages = with pkgs; [
          docker-compose
          ripgrep
          fd
          tree
        ];
      };

      programs = {
        fish = {
          enable = true;
          interactiveShellInit = # fish
            ''
              set -g fish_greeting # disable greeting
              bind ctrl-c cancel-commandline
            '';
        };
        git.enable = true;
        neovim = {
          enable = true;
          viAlias = true;
          configure = {
            customRC = ''
              set mouse=""
              set textwidth=80
              set formatoptions=cqjrol

              set cursorline
              set signcolumn=yes
              set list
              set listchars=tab:▸\ 
              set linebreak

              set wildmode=longest:full,full
              set wildignorecase

              set nowrapscan
              set ignorecase
              set smartcase

              set scrolloff=3
              set sidescrolloff=15

              " marks
              set jumpoptions=view

              " split
              set splitbelow
              set splitright

              " undo
              set undofile
              set undolevels=5000

              " indents
              set shiftwidth=2
              set expandtab

              xnoremap < <gv
              xnoremap > >gv
            '';
          };
        };
        htop = {
          enable = true;
          settings = {
            hide_kernel_threads = true;
            hide_userland_threads = true;
            show_program_path = false;
          };
        };
      };

      zramSwap.enable = true;

      boot = {
        initrd.systemd.enable = true;
        kernelParams = [ "zfs.zfs_arc_max=${toString (512 * 1024 * 1024)}" ];
        loader.timeout = 1;
      };

      networking = {
        firewall = {
          logRefusedConnections = false;
          logRefusedUnicastsOnly = false;
        };
        useNetworkd = true;
        useDHCP = false;
      };
      systemd.network = {
        wait-online.anyInterface = true;
        networks."10-uplink" = rec {
          name = "eth0";
          matchConfig.PermanentMACAddress = "72:33:71:b0:95:34";
          DHCP = "yes";
          dhcpV4Config = {
            RouteMetric = 100;
            UseMTU = true;
          };
          networkConfig.IPv6AcceptRA = false;
        };
        links."10-uplink" = {
          matchConfig.PermanentMACAddress = "72:33:71:b0:95:34";
          linkConfig = {
            Name = "eth0";
            WakeOnLan = "off";
          };
        };
      };

      system.stateVersion = "25.05";

      # ZFS
      networking.hostId = with builtins; substring 0 8 (hashString "md5" config.networking.hostName);
      services.zfs.trim.enable = false;
      disko.devices = {
        disk.disk0 = {
          device = "/dev/sda";
          type = "disk";
          content = {
            type = "gpt";
            partitions = {
              boot = {
                size = "1M";
                type = "EF02";
              };
              ESP = {
                size = "512M";
                type = "EF00";
                content = {
                  type = "filesystem";
                  format = "vfat";
                  mountpoint = "/boot";
                  mountOptions = [ "umask=0077" ];
                };
              };
              root = {
                size = "100%";
                content = {
                  type = "zfs";
                  pool = "zroot";
                };
              };
            };
          };
        };
        zpool.zroot = {
          type = "zpool";
          options = {
            ashift = "12";
            autotrim = "on";
          };
          rootFsOptions = {
            acltype = "posixacl";
            canmount = "off";
            dnodesize = "auto";
            normalization = "formD";
            relatime = "on";
            xattr = "sa";
            mountpoint = "none";
            compression = "lz4";
            "com.sun:auto-snapshot" = "false";
          };
          datasets = {
            rootfs = {
              mountpoint = "/";
              options.mountpoint = "legacy";
              type = "zfs_fs";
            };
            nix = {
              mountpoint = "/nix";
              options.mountpoint = "legacy";
              type = "zfs_fs";
            };
          };
        };
      };
    };
in
{
  flake.nixosConfigurations.nixos = inputs.nixpkgs.lib.nixosSystem {
    modules = [
      inputs.disko.nixosModules.default
      inputs.vscode-server.nixosModules.default

      cfg
      ./hw-config.nix
    ];
  };
}
