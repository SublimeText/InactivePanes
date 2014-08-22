"""Provides a settings abstraction class.

Exported classes:
    * Settings
"""

# Python 2 backwards compat
try:
    basestring
except NameError:
    basestring = str


class Settings(object):

    """ST settings abstraction that helps with default values and running a callback when changed.

    The main purpose is to always provide the correct value of a setting or a default, if set, under
    the same identifier (here: attribute). The settings auto-update by default and a custom callback
    may be specified that is called whenever one of the tracked settings value changes. Note that
    this is different to Sublimes `settings.add_on_change` as that will be called when any
    containing setting *could* have changed, while we only want it if the specified setting actually
    changed.

    Methods:
        * __init__(settings_obj, settings, callback=None, auto_update=True):
        * update()
        * has_changed()
        * get_state()
        * get_real_state()
        * set_callback(callback, auto_update=True)
        * clear_callback(clear_auto_update=False)
    """

    # Static class variables
    KEY = "__settings_abstr"

    # Instance variables
    _sobj = None
    _settings = None
    _callback = None
    _registered = False

    def __init__(self, settings_obj, settings, callback=None, auto_update=True):
        """Create a new instance.

        `settings` should be provided as a dict of tuples and attribute names should not be one of
        the existing functions. And of course they should be valid attribute names.

        Example call:
        Settings(
            sublime.load_settings("Preferences.sublime-settings"),
            settings=dict(
                attr_name_to_save_as=('settings_key_to_read_from', 'default_value'),
                attr_name_to_save_as2='settings_key_to_read_from_with_default_None',
                attr_name_and_settings_key_with_default_None=None
                #, ...
            ),
            callback=on_settings_changed,  # optional, callback
            auto_update=True  # optional, bool (whether the attributes should be kept up to date)
        )

        For the callback and auto_update parameters, refer to `set_callback`.
        """
        self._sobj = settings_obj

        for k, v in settings.items():
            if v is None:
                # Use the attr name as settings key and `None` as default
                settings[k] = (k, None)
            if isinstance(v, basestring):
                # Set default to `None` if a string was supplied
                settings[k] = (v, None)
        self._settings = settings

        self.update()
        self.set_callback(callback, auto_update)

    def __del__(self):
        """Deregister callback when destructing."""
        self.clear_callback(True)

    def update(self):
        """Read all the settings and save them in their respective attributes."""
        for attr, (name, def_value) in self._settings.items():
            setattr(self, attr, self._sobj.get(name, def_value))

    def _on_change(self):
        """Test if the tracked settings have changed and run a callback if specified."""
        if self.has_changed():
            self.update()
            if self._callback:
                self._callback()

    def _register(self, callback):
        self._registered = True
        self._sobj.add_on_change(self.KEY, callback)

    def _unregister(self):
        self._registered = False
        self._sobj.clear_on_change(self.KEY)

    def has_changed(self):
        """Return a boolean whether the cached settings differ from the settings object."""
        return self.get_state() != self.get_real_state()

    def get_state(self):
        """Return a dict with the tracked settings and their cached values.

        Does NOT use the attribute names but the setting keys.
        With the example from __init__: `{"settings_key_to_read_from": 'current_value'}`.
        """
        return dict((name, getattr(self, attr))
                    for attr, (name, _) in self._settings.items())

    def get_real_state(self):
        """Return a dict with the tracked settings and their actual values from the settings obj.

        Does NOT use the attribute names but the setting keys.
        With the example from __init__: `{"settings_key_to_read_from": 'current_value'}`.
        """
        return dict((name, self._sobj.get(name, def_value))
                    for name, def_value in self._settings.values())

    def set_callback(self, callback=None, auto_update=True):
        """Register `callback` to be called whenever a tracked setting's value changes.

        If `auto_update` is true, automatically update the attributes when the settings change. This
        always happens when a callback is set, thus resulting in the values being up-to-date when
        the callback is called.

        Return the previous callback if any.
        """
        if callback is not None and not callable(callback):
            raise TypeError("callback must be callable or None")

        register = bool(auto_update or callback)
        old_cb = self.clear_callback(not register)
        self._callback = callback
        if not self._registered and register:
            self._register(self._on_change)

        return old_cb

    def clear_callback(self, clear_auto_update=False):
        """Clear the callback set with set_callback and return it in the process.

        clear_auto_update=True will also remove auto-updating the attributes and `get_state`, if
        previously enabled.
        """
        old_cb = self._callback
        self._callback = None
        if self._registered and clear_auto_update:
            self._unregister()
        return old_cb
