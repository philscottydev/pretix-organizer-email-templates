# Release Checklist — pretix-organizer-email-templates

## For each new release

### 1. Bump version (two files)
- [ ] `pretix_organizeremailtemplates/__init__.py` — update `__version__`
- [ ] `pretix_organizeremailtemplates/apps.py` — update `PretixPluginMeta.version`

### 2. Update README.rst changelog
- [ ] Add entry at top of Changelog section

### 3. Commit
```bash
git add pretix_organizeremailtemplates/__init__.py pretix_organizeremailtemplates/apps.py README.rst
git commit -m "chore: bump version to vX.Y.Z"
git push origin main
```

### 4. Create annotated tag and GitHub release
```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes "## Changes\n- ..." --latest
```

### 5. Reinstall on server
```bash
sudo -u pretix /var/pretix/venv/bin/pip install -e /var/pretix-plugins/pretix-organizer-email-templates/
systemctl restart pretix-web pretix-worker
```

### 6. Verify
```bash
/var/pretix/venv/bin/python -c "import pretix_organizeremailtemplates; print(pretix_organizeremailtemplates.__version__)"
```

## Note on pretix update checker

Pretix's built-in update checker uses a proprietary registry at `https://pretix.eu/.update_check/`. Custom plugins not registered with pretix GmbH will always show "?" for latest version — this is expected behaviour and not a configuration error. GitHub releases serve as the changelog record for maintainers.
