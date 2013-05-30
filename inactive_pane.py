import os
import shutil
import re

import sublime
import sublime_plugin

ST2 = int(sublime.version()) < 3000

# We have to record the module path when the file is loaded because
# Sublime Text changes it later (on ST2).
module_path = os.getcwdu() if ST2 else os.path.dirname(__file__)
module_name = os.path.split(module_path)[1]


class Settings(object):
    """Provides various helping functions for wrapping the sublime settings objects.

    `settings` should be provided as a dict of tuples and attribute names should not be one of the
    existing functions. And of course they should be valid attribute names.

    Example constructor:
    Settings(
        sublime.load_settings("Preferences.sublime-settings"),
        dict(
            attribute_name_to_save_as=('settings_key_to_read_from', 'default_value')
            #, ...
        ),
        settings_changed  # optional, callback
    )

    `settings_changed` will be called when the registered settings changed, and this time for real.
    Sublime Text currently behaves weird with `add_on_change` calls and the callback is run more
    often than it should be (as in, the specified setting didn't actually change), this wrapper
    however tests if one of the values has changed and then calls the callback.
    `update()` is called before the callback.

    Methods:
        * update() - Reads all the settings and saves them in their respective attributes.
        * has_changed() - Returns a boolean if the currently cached settings differ.
        * register(callback) - runs `add_on_change` for all settings.
        * unregister() - See above, `clear_on_change`.
    """
    _sobj = None
    _settings = None
    _callback = None

    def __init__(self, settings_obj, settings, callback=None):
        self._sobj = settings_obj
        self._settings = settings
        self._callback = callback

        self.update()
        if self._callback:
            self.register(self._on_change)

    def update(self):
        for attr, (name, value) in self._settings.items():
            setattr(self, attr, self._sobj.get(name, value))

    def _on_change(self):
        # Only trigger if relevant settings changed
        if self.has_changed():
            print("changed!")
            self.update()
            self._callback()

    def has_changed(self):
        for attr, (name, value) in self._settings.items():
            if getattr(self, attr) != self._sobj.get(name, value):
                return True

        return False

    def register(self, callback):
        for name, _ in self._settings.values():
            self._sobj.add_on_change(name, callback)

    def unregister(self):
        for name, _ in self._settings.values():
            self._sobj.clear_on_change(name)


class InactivePanes(object):
    """A dummy class which holds this plugin's methods.
    Maybe I can think of a better way to structure plugins like these but for now this'll do it
    """
    _settings  = None
    _refreshed = False

    def init(self):
        self._settings = Settings(
            sublime.load_settings('Preferences.sublime-settings'),
            dict(
                gray_scale=('fade_inactive_panes_gray_scale', .2),
                # Including this to regenerate the color scheme immediately afterwards
                _color_scheme=('color_scheme', None)
            ),
            self.cycling_reset
        )

        # Boot up
        self.cycling_reset()

    def deinit(self):
        self._settings.unregister()
        self.reset(True)

    def cycling_reset(self, disable=False):
        """Retry accessing the active window until it is available
        """
        if not sublime.active_window():
            sublime.set_timeout(lambda: self.cycling_reset, 50)
        else:
            self.reset(disable)

    def reset(self, disable=False):
        """Delete temporaryly generated dimmed files.
        """
        # "Disable" the plugin first (as in, remove all references to dimmed schemes).
        self.refresh_views(True)

        def onerror(function, path, excinfo):
            sublime.error_message("Warning!\n"
                                  "Could not remove '%s'\n\n"
                                  "Error with function '%s': %s"
                                  % (path, function, excinfo))

        # Delete all subdirs of this module.
        for root, dirs, files in os.walk(module_path):
            if '.git' in dirs:
                dirs.remove('.git')  # do not iterate over .git or subdirs
            for di in dirs:
                shutil.rmtree(os.path.join(root, di), onerror=onerror)

        if not disable:
            self.refresh_views()

    def refresh_views(self, disable=False):
        # We need this because ST for some reason calls on_activated with void views on startup
        self._refreshed = True
        active_view_id = sublime.active_window().active_view().id()
        for window in sublime.windows():
            for v in window.views():
                if v.settings().get('is_widget'):
                    continue

                if disable or v.id() == active_view_id:
                    self.on_activated(v)
                else:
                    self.on_deactivated(v)

    def create_inactive_scheme(self, scheme):
        """This is where the fun begins.
        """
        # Unfortunately, scheme paths start with "Packages/" and packages_path ends with
        # "Packages/", so we add a .. in the middle when we combine them.
        # TOCHECK: do absolute paths work?
        source_abs = os.path.normpath(os.path.join(sublime.packages_path(), "..", scheme))

        # `commonprefix()` isn't guaranteed to return a complete path, so we take the dirname to
        # get something real. All that really matters is that the path points unambiguously to one
        # color scheme, though we'd prefer for it to be as short as possible.
        #
        # TOCHECK: "Package/Inactive..." as path for scheme
        prefix = os.path.dirname(os.path.commonprefix([source_abs, module_path]))
        # `prefix` will most likely be the packages path.
        source_rel = os.path.relpath(source_abs, prefix)

        # Reconstruct the relative path inside of our module directory--we
        # have something of a shadow copy of the scheme.
        dest = os.path.join(module_path, source_rel)

        # Copy and dim the scheme if it does not exist
        if not os.path.isfile(dest):
            destdir = os.path.dirname(dest)
            if not os.path.isdir(destdir):
                try:
                    os.makedirs(destdir)
                except OSError as e:
                    sublime.error_message("Warning!\n"
                                          "Could not create folder '%s'.\n"
                                          "This means that this plugin will not work.\n\n"
                                          "Error: %s"
                                          % (destdir, e))
                    raise  # re raise to make sure that this plugin will not be executed further

            if ST2:
                shutil.copy(source_abs, dest)
            else:
                # ST3 does not unzip .sublime-packages, thus the `load_resource` API will be used.
                with open(dest, 'w') as f:
                    f.write(sublime.load_resource(scheme))

            print("[%s] Generating dimmed color scheme for '%s'" % (module_name, scheme))
            self.dim_scheme(dest)

        # Sublime Text only likes relative paths for its color schemes, with "/".
        return "Packages/%s/%s" % (module_name, source_rel.replace("\\", "/"))

    def dim_scheme(self, scheme):
        gray_scale = self._settings.gray_scale
        print("[%s] Gray scale: %s" % (module_name, gray_scale))

        def dim_rgb(match):
            rgb = list(match.groups())
            orig_scale = 1 - gray_scale
            # Average toward gray
            for i, c in enumerate(rgb):
                rgb[i] = int(int(c, 16) * orig_scale + 127 * gray_scale)

            return "#{0:02x}{1:02x}{2:02x}".format(*rgb)

        with open(scheme) as f:
            text = f.read()

        text = re.sub("#" + (r"([0-9a-fA-F]{2})" * 3), dim_rgb, text)
        with open(scheme, 'w') as f:
            f.write(text)

    # The actual event handlers
    def on_activated(self, view):
        if not view.file_name() and not view.is_scratch() and not view.is_dirty():
            print("[%s] What do we have here? A new and empty buffer?" % module_name)

        vsettings = view.settings()

        # Get the previous scheme of the current view (if it existed).
        default_scheme = vsettings.get('default_scheme')

        if default_scheme:
            vsettings.set('color_scheme', default_scheme)
            vsettings.erase('default_scheme')
        else:
            # Otherwise just erease our user-scheme
            vsettings.erase('color_scheme')

    def on_deactivated(self, view):
        if not view.buffer_id():
            return  # view was closed

        if not self._refreshed:
            # No business here, we wait for the plugin to refresh in order to ignore ST2's dummy
            # views that are passed sometimes.
            return

        vsettings = view.settings()

        # Reset to the base color scheme first if there was any
        # (in case ST was restarted).
        if module_name in vsettings.get('color_scheme'):
            self.on_activated(view)

        # Note: all "scheme" paths here are relative
        active_scheme = vsettings.get('color_scheme')
        vsettings.erase('color_scheme')
        default_scheme = vsettings.get('color_scheme')
        if active_scheme != default_scheme:
            # Because the settings do not equal after removing the view-specific setting the view's
            # color scheme is expicitly set so save it for later.
            vsettings.set('default_scheme', active_scheme)

        if self._view_on_top(view):
            # Potentially copy and dim the scheme
            inactive_scheme = self.create_inactive_scheme(active_scheme)
            vsettings.set('color_scheme', inactive_scheme)

    def _view_on_top(self, view):
        win = view.window()
        group, index = win.get_view_index(view)
        active_view = win.active_view_in_group(group)
        return active_view.buffer_id() == view.buffer_id()


# Use this local instance for all the references
inpanes = InactivePanes()


class InactivePaneCommand(sublime_plugin.EventListener):
    def on_activated(self, view):
        inpanes.on_activated(view)

    def on_deactivated(self, view):
        inpanes.on_deactivated(view)


# I don't use this currently but maybe it will come in hand when debugging other's issues
class ColorSchemeEmergencyResetCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        for window in sublime.windows():
            for view in window.views():
                vsettings = view.settings()
                vsettings.erase('color_scheme')
                vsettings.erase('default_scheme')

        print("All color schemes have been reset to your settings")


def plugin_loaded():
    # "Initialize" the instance here
    inpanes.init()


def plugin_unloaded():
    print("[%s] Deactivating..." % module_name)
    inpanes.deinit()

# ST2 backwards (and don't call it twice in ST3)
unload_handler = plugin_unloaded if ST2 else lambda: None

if ST2:
    plugin_loaded()
