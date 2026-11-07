# Sourced by CI steps that use STIR (see .github/workflows/stir.yml, "Find STIR's config files").
# Keeps STIR_CONFIG_DIR when it already points at STIR's config files, else uses the recorded folder.
if [ ! -f "${STIR_CONFIG_DIR:-/nonexistent}/radionuclide_info.json" ] && [ -s .stir_config_dir ]; then
  STIR_CONFIG_DIR="$(cat .stir_config_dir)"
  export STIR_CONFIG_DIR
fi
echo "STIR_CONFIG_DIR=${STIR_CONFIG_DIR:-unset}"
