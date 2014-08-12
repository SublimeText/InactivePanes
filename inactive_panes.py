import os
import shutil
import re
from functools import partial
from contextlib import contextmanager

import sublime
import sublime_plugin

try:
    from .settings import Settings
except:
    from settings import Settings

ST2 = int(sublime.version()) < 3000
DEBUG = True

if not ST2:
    basestring = str

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


class InactivePanesSettings(Settings):

    """Override _on_change handler to check for a changed color_scheme setting on a lower level."""

    _enabled = True

    def _on_change(self):
        # Don't check for changes, just update
        if not self._enabled:
            if self.has_changed():
                self.update()
            return

        # Only trigger if relevant settings changed
        if not self.has_changed():
            # Check if the underlying "color_scheme" (not-view setting) has changed.
            # For this we need to temporarily erase the setting.
            s = self._sobj
            # Disable to prevent an infinite recursive call chain.
            self._enabled = False
            dimmed_scheme = s.get("color_scheme")
            s.erase("color_scheme")
            base_scheme = s.get("color_scheme")[len('Packages/'):]
            s.set("color_scheme", dimmed_scheme)

            underlying_changed = (base_scheme not in dimmed_scheme
                                  or MODULE_NAME not in dimmed_scheme)
            self._enabled = True
            if not underlying_changed:
                return

        self.update()
        if self._callback:
            self._callback()

    @contextmanager
    def temp_disable(self):
        """Contextmanager to use when modifying the settings without calling the callback."""
        self._enabled = False
        yield
        self._enabled = True


class InactivePanes(object):

    """A dummy class which holds this plugin's methods.

    Maybe I can think of a better way to structure plugins like these but for now this'll do it.
    """

    _settings  = None
    _refreshed = False
    _dimmed_view_settings = dict()

    # Custom init and deinit

    def init(self):
        # Boot up
        self.cycling_reset()

    def deinit(self):
        self.cycling_reset(disable=True)

    # Core methods

    def cycling_reset(self, disable=False):
        """Retry accessing the active window until it is available."""
        if not sublime.active_window():
            sublime.set_timeout(self.cycling_reset, 50)
        else:
            self.reset(disable)

    def reset(self, disable=False):
        """Reset all views, delete generated dimmed files and set dimmed scheme(s) again."""
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
        """Iterate over all views and re- or unapply dimmed scheme(s)."""
        # We need this because ST for some reason calls "on_activated" with 'void' views on startup.
        self._refreshed = True

        active_view_id = sublime.active_window().active_view().id()
        for w in sublime.windows():
            for v in w.views():
                if v.settings().get('is_widget'):
                    # Does this even happen?
                    continue

                if disable or v.id() == active_view_id:
                    self.undim_view(v)
                else:
                    # Need to pass the window because `view.window()` is apparently `None` here ...
                    self.dim_view(v, w)

    def create_dimmed_scheme(self, source_rel, settings, force=False):
        """Create a new dimmed scheme out of source_rel with the given settings.

        Unless force=True, an already existing file will not be overwritten.
        Return the relative path to the dimmed scheme."""
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
        if force or not os.path.isfile(dest_abs):
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

            write_params = {}
            if ST2:
                with open(source_abs, 'r') as f:
                    data = f.read()
            else:
                # ST3 does not unzip .sublime-packages, thus the "load_resource" API will be used.
                data = sublime.load_resource(source_rel)
                write_params["encoding"] = 'utf-8'

            debug("Generating dimmed color scheme for '%s'" % source_rel)
            new_data = self.dim_scheme(data, settings)
            if not new_data:
                return

            with open(dest_abs, 'w', **write_params) as f:
                f.write(new_data)

        return dest_rel

    def dim_scheme(self, data, settings):
        """Dim a color scheme string and return it."""
        dim_color = settings.dim_color
        dim_strength = settings.dim_strength
        debug("Dim color: %s; Dim strength: %s" % (dim_color, dim_strength))

        # Check settings validity.
        if not isinstance(dim_strength, (int, float)) or dim_strength < 0 or dim_strength > 1:
            print("![%s] Dim strength is not a number between 0 and 1!" % (MODULE_NAME))
            return

        re_rgb = re.compile("#" + (r"([0-9A-F]{2})" * 3), re.I)
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

    def undim_view(self, view):
        """Undo our dimming and restore potential prev view-specific color scheme."""
        if not self._refreshed:
            return

        # Remove from our dimmed settings list and unregister before we reset the scheme.
        vsettings = self._dimmed_view_settings.pop(view.id(), None)
        if vsettings:
            vsettings.clear_callback(True)

        s = view.settings()

        # Get the previous scheme of the current view (if it existed).
        # Note that we always check for this.
        default_scheme = s.get('default_scheme')

        if default_scheme:
            s.set('color_scheme', default_scheme)
            s.erase('default_scheme')
        else:
            # Otherwise just erase our dimmed scheme
            s.erase('color_scheme')

    # This dict is static
    _settings_dict = dict(
        dim_strength=('inactive_panes_dim_strength', .2),
        dim_color=('inactive_panes_dim_color', '#7F7F7F'),
        # Including this in order to get a notification when the scheme has changed
        _color_scheme=('color_scheme', None)
    )

    def dim_view(self, view, window=None):
        """Dim a view, if it's visible, and store prev view-specific setting."""
        if not self._refreshed:
            return

        s = view.settings()

        # Reset to the base color scheme first if there was any
        # (in case ST was restarted).
        if MODULE_NAME in s.get('color_scheme') or view.id() in self._dimmed_view_settings:
            debug("This should not have happened: %r %r"
                  % (view.file_name(), s.get('color_scheme')))
            self.undim_view(view)

        # Don't bother any more if the current view is not on top
        if not self.view_is_visible(view, window):
            return

        self.redim_view(view, force=False)

    def redim_view(self, view, force=True):
        """Dim a view and store prev view-specific setting.

        Only call this if you know for sure that the view should be dimmed.
        """
        s = view.settings()

        # Register on_change handler
        if view.id() not in self._dimmed_view_settings:
            vsettings = InactivePanesSettings(
                s,
                settings=self._settings_dict,
                callback=partial(self.on_view_settings_changed, view)
            )
            self._dimmed_view_settings[view.id()] = vsettings
            redim = False
        else:
            vsettings = self._dimmed_view_settings[view.id()]
            redim = True

        # Temporarily disable our hook to prevent infinite recursive call chains
        # Note: all "scheme" paths here are relative
        with vsettings.temp_disable():
            active_scheme = s.get('color_scheme')
            # Determine the scheme to dim
            if redim:
                if MODULE_NAME in active_scheme:
                    if s.get("default_scheme"):
                        active_scheme = s.get("default_scheme")
                    else:
                        # The underlying scheme possibly changed
                        s.erase('color_scheme')
                        active_scheme = s.get('color_scheme')
                # View-specific setting was overwritten
                else:
                    default_scheme = active_scheme
                    s.set('default_scheme', active_scheme)
            else:
                s.erase('color_scheme')
                default_scheme = s.get('color_scheme')
                if active_scheme != default_scheme:
                    # Because the settings do not equal after removing the view-specific setting,
                    # the view's color scheme is explicitly set, so we save it for restoring later.
                    s.set('default_scheme', active_scheme)

            # Potentially copy and dim the scheme
            inactive_scheme = self.create_dimmed_scheme(active_scheme, vsettings, force)
            if inactive_scheme:
                s.set('color_scheme', inactive_scheme)
            else:
                # Reset if failed
                s.set('color_scheme', active_scheme)
                s.erase('default_scheme')

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

    def on_view_settings_changed(self, view):
        # view is assumed to be dimmed
        assert view.id() in self._dimmed_view_settings  # TODO remove
        debug("Settings changed for %s" % view.file_name())
        self.redim_view(view)


# Use this local instance for all the references
inpanes = InactivePanes()


class InactivePanesListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        if ST2:
            sublime.set_timeout(50, lambda: self.on_activated_async(view))

    def on_activated_async(self, view):
        # For some weird reason, ST2 fires this event twice for every view,
        # once with (and no corresponding deactivation) and once without an associated .window().
        # We'll try to reset our color scheme references at the earliest point possible though.

        # Don't remove color schemes from widgets (e.g. output panels)
        if not (view.settings().get('is_widget') or view.window() is None):
            inpanes.undim_view(view)

    def on_deactivated(self, view):
        if ST2:
            sublime.set_timeout(50, lambda: self.on_deactivated_async(view))

    def on_deactivated_async(self, view):
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

    """Removes view-specific color scheme settings (including our temporary)."""

    def run(self):
        for window in sublime.windows():
            for view in window.views():
                s = view.settings()
                s.erase('color_scheme')
                s.erase('default_scheme')

        print("All color scheme settings have been reset")


def plugin_loaded():
    inpanes.init()


def plugin_unloaded():
    debug("Deactivating...")
    inpanes.deinit()

# ST2 backwards (and don't call it twice in ST3)
unload_handler = plugin_unloaded if ST2 else lambda: None

if ST2:
    plugin_loaded()
