{ lib, inputs, ... }:
{
  imports = with inputs; [
    git-hooks-nix.flakeModule
    treefmt-nix.flakeModule
  ];

  perSystem =
    { pkgs, config, ... }:
    {
      devShells.default = config.pre-commit.devShell.overrideAttrs {
        packages = with pkgs; [
          bashInteractive
          just
          nixos-anywhere
        ];
      };

      pre-commit.settings.hooks = {
        treefmt = {
          enable = true;
          package = config.treefmt.build.wrapper;
        };
        statix = {
          enable = true; # check. not everything can be fixed, but we need to know what
          settings.format = "stderr";
          settings.config =
            ((pkgs.formats.toml { }).generate "statix.toml" {
              disabled = config.treefmt.programs.statix.disabled-lints;
            }).outPath;
        };
      };

      treefmt = {
        projectRootFile = "flake.nix";
        programs = {
          nixfmt.enable = true;
          deadnix.enable = true;
          statix = {
            enable = true; # fix, if possible
            disabled-lints = [ "repeated_keys" ];
          };
        };
      };
    };
}
