import os
import shutil
import re

import sublime
import sublime_plugin

ST2 = int(sublime.version()) < 3000
DEBUG = True

# TODO remove ST2 support. That thing is ridiculous and fires on_activated events
# at everything that doesn't take cover in time. Would ease maintaining this a lot.
# Did I mention that ST2 loads User settings AFTER the plugin, which results in color schemes to be
# dimmed twice if the settings are not our default? Well, it makes sense but is still annoying.


# We have to record the module path when the file is loaded because
# Sublime Text 2 changes it later.
# On ST3 we could use os.path.join(sublime.packages_path(), __package__), but sadly this method is
# not available until the API has loaded.
def get_module_path():
    if ST2:
        return os.getcwdu(), False

    dir_name = os.path.dirname(__file__)
    # Check if we are in a .sublime-package and normalize the path
    if dir_name.endswith(".sublime-package"):
        return (re.sub(r"(?:Installed )?Packages([\\/][^\\/]+)\.sublime-package$",
                       r"Packages\1", dir_name),
                True)
    else:
        return dir_name, False

MODULE_PATH, _ = get_module_path()
MODULE_NAME = os.path.split(MODULE_PATH)[1]

# Emergency stop. You'll thank me if you ever experience what I did.
if MODULE_PATH == sublime.packages_path():
    import sys
    sys.exit(1)

# ST3 had a bug where we needed to copy to a different package dir because otherwise plugins from
# archived packages would not be loaded. Since this has been fixed, remove it if it still exists.
# See: http://www.sublimetext.com/forum/viewtopic.php?f=3&t=12564
if os.path.exists(MODULE_PATH + '_'):
    try:
        shutil.rmtree(MODULE_PATH + '_')
    except Exception as e:
        print("Unable to remove the deprecated '%s_' dir: %s %s"
              % (MODULE_NAME, e.__class__.__name__, e))


def debug(msg):
    if DEBUG:
        print("[%s] %s" % (MODULE_NAME, msg))


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
        on_settings_changed  # optional, callback
    )

    `settings_changed` will be called when the registered settings changed, and this time for real.
    Sublime Text currently behaves weird with `add_on_change` calls and the callback is run more
    often than it should be (as in, the specified setting didn't actually change), this wrapper
    however tests if one of the values has changed and then calls the callback.
    `update()` is called before the callback.

    Methods:
        * update()
            Reads all the settings and saves them in their respective attributes.
        * has_changed()
            Returns a boolean if the currently cached settings differ.
        * register(callback)
            Runs `add_on_change` for all settings defined with `callback` param
        * unregister()
            See above, `clear_on_change`.
        * get_state()
            Returns a dict with the tracked settings as keys and their values (not the attribute
            names). With the above example: `{"settings_key_to_read_from": 'current_value'}`.
    """
    _sobj = None
    _settings = None
    _callback = None

    def __init__(self, settings_obj, settings, callback=None):
        self._sobj = settings_obj
        self._settings = settings
        self._callback = callback

        self.update()
        if callable(self._callback):
            self.register(self._on_change)

    def update(self):
        for attr, (name, def_value) in self._settings.items():
            setattr(self, attr, self._sobj.get(name, def_value))

    def _on_change(self):
        # Only trigger if relevant settings changed
        if self.has_changed():
            self.update()
            self._callback()

    def has_changed(self):
        for attr, (name, def_value) in self._settings.items():
            if getattr(self, attr) != self._sobj.get(name, def_value):
                return True

        return False

    def register(self, callback):
        for name, _ in self._settings.values():
            self._sobj.add_on_change(name, callback)

    def unregister(self):
        for name, _ in self._settings.values():
            self._sobj.clear_on_change(name)

    def get_state(self):
        return dict((name, self._sobj.get(name, def_value))
                    for name, def_value in self._settings.values())


class InactivePanes(object):
    """A dummy class which holds this plugin's methods.
    Maybe I can think of a better way to structure plugins like these but for now this'll do it
    """
    _settings  = None
    _refreshed = False

    ### Custom init and deinit

    def init(self):
        self._settings = Settings(
            sublime.load_settings('Preferences.sublime-settings'),
            settings=dict(
                dim_strength=('inactive_panes_dim_strength', .2),
                dim_color=('inactive_panes_dim_color', '#7F7F7F'),
                # Including this in order to get a notification when the scheme has changed
                _color_scheme=('color_scheme', None)
            ),
            callback=self.cycling_reset
        )

        # Boot up
        self.cycling_reset()

    def deinit(self):
        self._settings.unregister()
        self.cycling_reset(True)

    ### Utitily functions

    def cycling_reset(self, disable=False):
        """Retry accessing the active window until it is available
        """
        if not sublime.active_window():
            sublime.set_timeout(self.cycling_reset, 50)
        else:
            # Just disable the package if dim strength is `0`.
            self.reset(disable or self._settings.dim_strength == 0)

    def reset(self, disable=False):
        """Reset all views, delete temporarily generated dimmed files and set dimmed scheme(s) again
        """
        # "Disable" the plugin first (as in, remove all references to dimmed schemes).
        self.refresh_views(True)

        def onerror(function, path, excinfo):
            sublime.error_message("Warning!\n"
                                  "Could not remove '%s'\n\n"
                                  "Error with function '%s': %s"
                                  % (path, function, excinfo))

        # Delete all subdirs of this module to cleanup leftover schemes
        # (and regenerate them in case settings have changed during downtime)
        for root, dirs, _ in os.walk(MODULE_PATH):
            if '.git' in dirs:
                dirs.remove('.git')  # do not iterate over .git or its subdirs
            for d in dirs:
                shutil.rmtree(os.path.join(root, d), onerror=onerror)

        if not disable:
            self.refresh_views()

    def refresh_views(self, disable=False):
        """Iterate over all views and re- or unapply dimmed scheme(s)
        """
        # We need this because ST for some reason calls "on_activated" with void views on startup.
        self._refreshed = True

        active_view_id = sublime.active_window().active_view().id()
        for w in sublime.windows():
            for v in w.views():
                if v.settings().get('is_widget'):
                    continue

                if disable or v.id() == active_view_id:
                    self.undim_view(v)
                else:
                    # Need to pass the window because `view.window()` is apparently `None` here ...
                    self.dim_view(v, w)

    def create_inactive_scheme(self, source_rel):
        """This is where the fun begins.
        """
        # Assume scheme paths always look like this "Packages/.../*.tmTheme" (which means the root
        # is the Data directory), because nothing else seems to work.
        prefix = "Packages/"
        if not source_rel.startswith(prefix):
            # However, if this is not true ...
            sublime.message_dialog(
                "Warning!\n"
                "Your setup seems to use an unrecognized color scheme setting which %s does not "
                "take care of. Please create an issue at this package's repository or a post in "
                "the forum and mention your color_scheme path: '%s'."
                % (MODULE_NAME, source_rel)
            )
            return

        # Very unlikely to change but "packages_path" is not available at module load time.
        data_path = os.path.normpath(os.path.join(sublime.packages_path(), ".."))

        # Some path math~
        source_abs = os.path.join(data_path, *source_rel.split("/"))
        # Reconstruct the relative path inside of our module directory; we have something of a
        # shadow copy of the scheme.
        dest_rel = prefix + "%s/%s" % (MODULE_NAME, source_rel[len(prefix):])
        dest_abs = os.path.join(data_path, *dest_rel.split("/"))

        # Copy and dim the scheme if it does not exist
        if not os.path.isfile(dest_abs):
            destdir = os.path.dirname(dest_abs)
            if not os.path.isdir(destdir):
                try:
                    os.makedirs(destdir)
                except OSError as e:
                    sublime.error_message("Warning!\n"
                                          "Could not create folder '%s'.\n"
                                          "This means that this plugin will not work.\n\n"
                                          "Error: %s"
                                          % (destdir, e))
                    raise  # re-raise to make sure that this plugin will not be executed further

            if ST2:
                with open(source_abs, 'r') as f:
                    data = f.read()
                open_file = lambda: open(dest_abs, 'w')
            else:
                # ST3 does not unzip .sublime-packages, thus the "load_resource" API will be used.
                data = sublime.load_resource(source_rel)
                open_file = lambda: open(dest_abs, 'w', encoding='utf-8')

            debug("Generating dimmed color scheme for '%s'" % source_rel)
            new_data = self.dim_scheme(data)
            if not new_data:
                return

            with open_file() as f:
                f.write(new_data)

        return dest_rel

    def dim_scheme(self, data):
        """Dim a color scheme string and return it.
        """
        dim_color = self._settings.dim_color
        dim_strength = self._settings.dim_strength
        debug("Dim color: %s; Dim strength: %s" % (dim_color, dim_strength))

        # Check settings validity.
        if not isinstance(dim_strength, (int, float)) or dim_strength < 0 or dim_strength > 1:
            print("![%s] Dim strength is not a number between 0 and 1!" % (MODULE_NAME))
            return

        re_rgb = re.compile("#" + (r"([0-9a-fA-F]{2})" * 3))
        dim_rgb = re_rgb.match(dim_color)
        if not dim_rgb or not len(dim_color) == 7:
            print("![%s] Dim color must be of format '#RRGGBB' where the colors are hexadecimal "
                  "digits from 0 to F!" % (MODULE_NAME))
            return

        # Pre-calc the dim rgb fractions because they are static.
        dim_rgb_v = tuple(int(int(c, 16) * dim_strength) for c in dim_rgb.groups())

        def dim_and_repl_rgb(match):
            rgb = match.groups()
            orig_strength = 1 - dim_strength

            # Average toward dim_color.
            rgb = [int(int(rgb[i], 16) * orig_strength) + dim_rgb_v[i]
                   for i in range(3)]

            return "#{0:02x}{1:02x}{2:02x}".format(*rgb)

        return re_rgb.sub(dim_and_repl_rgb, data)

    ### The actual event handlers

    def undim_view(self, view):
        """Undo our dimming and restore potential prev view-specific color scheme."""
        if not self._refreshed:
            return

        vsettings = view.settings()

        # Get the previous scheme of the current view (if it existed).
        default_scheme = vsettings.get('default_scheme')

        if default_scheme:
            vsettings.set('color_scheme', default_scheme)
            vsettings.erase('default_scheme')
        else:
            # Otherwise just erease our user-scheme
            vsettings.erase('color_scheme')

    def dim_view(self, view, window=None):
        """Dim a view with our settings, if it's visible, and store prev view-spcific setting."""
        if not self._refreshed:
            return

        vsettings = view.settings()

        # Reset to the base color scheme first if there was any
        # (in case ST was restarted).
        if MODULE_NAME in vsettings.get('color_scheme'):
            self.undim_view(view)

        # Don't bother any more if the current view is not on top
        if not self.view_is_visible(view, window):
            return

        # Note: all "scheme" paths here are relative
        active_scheme = vsettings.get('color_scheme')
        vsettings.erase('color_scheme')
        default_scheme = vsettings.get('color_scheme')
        if active_scheme != default_scheme:
            # Because the settings do not equal after removing the view-specific setting the view's
            # color scheme is expicitly set so save it for later.
            vsettings.set('default_scheme', active_scheme)

        # Potentially copy and dim the scheme
        inactive_scheme = self.create_inactive_scheme(active_scheme)
        if inactive_scheme:
            vsettings.set('color_scheme', inactive_scheme)

    def view_is_visible(self, view, window=None):
        """Check if specified view is on top of its group => it's actually visible."""
        window = window or view.window()
        if not window:
            return

        group, index = window.get_view_index(view)
        active_view = window.active_view_in_group(group)
        if not active_view:
            # ST2: This is always None when switching tabs in the same group, but if an unnamed
            # tabs was to be returned, so test if that happened.
            return window.active_group() != group

        return active_view.id() == view.id()


# Use this local instance for all the references
inpanes = InactivePanes()


class InactivePanesListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        # For some weird reason, ST2 fires this event twice for every view,
        # once with (and no corresponding deactivation) and once without an associated .window().
        # We'll try to reset our color scheme references at the earliest point possible though.

        # Don't remove color schemes from widgets (e.g. output panels)
        if not (view.settings().get('is_widget') or view.window() is None):
            inpanes.undim_view(view)

    def on_deactivated(self, view):
        if (
            # Invalid argument
            view is None
            # We have a widget here, not of interest
            or view.settings().get('is_widget') or view.window() is None
            # view was closed
            or not view.buffer_id()
        ):
            return
        inpanes.dim_view(view)

    # This is mainly for opening entire projects
    def on_load(self, view):
        # Remove references to possibly now non-existant schemes
        # (on ST2 this should've happened already)
        inpanes.undim_view(view)
        # Then dim all (visible) but the active
        # (on ST2, non-visible views seem to have no window associated at this time)
        if view.window() and view.id() != view.window().active_view().id():
            inpanes.dim_view(view)


# I don't use this currently but maybe it will come in hand when debugging other's issues
class ColorSchemeEmergencyResetCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        for window in sublime.windows():
            for view in window.views():
                vsettings = view.settings()
                vsettings.erase('color_scheme')
                vsettings.erase('default_scheme')

        print("All color schemes have been reset")


def plugin_loaded():
    # "Initialize" the instance here
    inpanes.init()


def plugin_unloaded():
    debug("Deactivating...")
    inpanes.deinit()

# ST2 backwards (and don't call it twice in ST3)
unload_handler = plugin_unloaded if ST2 else lambda: None

if ST2:
    plugin_loaded()
