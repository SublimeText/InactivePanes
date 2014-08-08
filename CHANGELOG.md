File History Changelog
======================

~current iteration~
-------------------

- Remove the old workaround that involved saving generated files to a different
  package ("InactivePanes_")


v0.3.1 (2013-05-31)
-------------------

- Add setting to set a costom color to dim to
* **Note**: The `fade_inactive_panes_gray_scale` setting has been renamed to `inactive_panes_dim_strength`
- The plugin won't do anything now if dim strength is set to `0`


v0.3.0 (2013-05-31)
-------------------

- Make the plugin work when installed via Package Control in ST3 (.sublime-package)
- Fix error when to-be-dimmed color scheme contains unicode chars in ST3


v0.2.2 (2013-05-30)
-------------------

- Only dim inactive views when they are actually visible (on top of a group)
- Remove the delay when changing focus
- Fix even more errors

v0.2.1 (2013-05-06)
-------------------

- Really fix (hopefully) all errors
- Do not error when changing color schemes (and update all views accordingly)

v0.2.0 (2013-05-06)
-------------------

- Add support for ST3
- Fix errors when disabling or enabling the package
- Make reloading when settings changed more responsive
- Remove unneeded `fade_inactive_panes` setting, you can ignore the whole package now instead
- Rename setting: `fade_inactive_panes_grey_scale` to `fade_inactive_panes_gray_scale` (-> gray)


v0.1.0 (2013-05-03)
-------------------

- Split from Origami, initial commit
