#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import operator
import math

import gtk
import gobject

from tryton.common import RPCExecute, RPCException


class SelectionMixin(object):

    def __init__(self, *args, **kwargs):
        super(SelectionMixin, self).__init__(*args, **kwargs)
        self.selection = None
        self.inactive_selection = []
        self._last_domain = None
        self._values2selection = {}
        self._domain_cache = {}

    def init_selection(self, key=None):
        if key is None:
            key = tuple(sorted((k, None)
                    for k in self.attrs.get('selection_change_with') or []))
        selection = self.attrs.get('selection', [])[:]
        if (not isinstance(selection, (list, tuple))
                and key not in self._values2selection):
            try:
                if self.attrs.get('selection_change_with'):
                    selection = RPCExecute('model', self.model_name, selection,
                        dict(key))
                else:
                    selection = RPCExecute('model', self.model_name, selection)
            except RPCException:
                selection = []
            self._values2selection[key] = selection
        elif key in self._values2selection:
            selection = self._values2selection[key]
        if self.attrs.get('sort', True):
            selection.sort(key=operator.itemgetter(1))
        self.selection = selection[:]
        self.inactive_selection = []

    def update_selection(self, record, field):
        if not field:
            return

        if 'relation' not in self.attrs:
            change_with = self.attrs.get('selection_change_with') or []
            args = record._get_on_change_args(change_with)
            del args['id']
            key = args.items()
            key.sort()
            self.init_selection(tuple(key))
        else:
            domain = field.domain_get(record)
            context = record[self.field_name].context_get(record)
            domain_cache_key = str(domain) + str(context)
            if domain_cache_key in self._domain_cache:
                self.selection = self._domain_cache[domain_cache_key]
                self._last_domain = (domain, context)
            if (domain, context) == self._last_domain:
                return

            try:
                result = RPCExecute('model', self.attrs['relation'],
                    'search_read', domain, 0, None, None, ['rec_name'],
                    context=context)
            except RPCException:
                result = False
            if isinstance(result, list):
                selection = [(x['id'], x['rec_name']) for x in result]
                selection.append((None, ''))
                self._last_domain = (domain, context)
                self._domain_cache[domain_cache_key] = selection
            else:
                selection = []
                self._last_domain = None
            self.selection = selection[:]
            self.inactive_selection = []

    def get_inactive_selection(self, value):
        if 'relation' not in self.attrs:
            return ''
        for val, text in self.inactive_selection:
            if str(val) == str(value):
                return text
        else:
            try:
                result, = RPCExecute('model', self.attrs['relation'], 'read',
                    [value], ['rec_name'])
                self.inactive_selection.append((result['id'],
                        result['rec_name']))
                return result['rec_name']
            except RPCException:
                return ''


def selection_shortcuts(entry):
    def key_press(widget, event):
        if (event.type == gtk.gdk.KEY_PRESS
                and event.state & gtk.gdk.CONTROL_MASK
                and event.keyval == gtk.keysyms.space):
            widget.popup()
    entry.connect('key_press_event', key_press)
    return entry


class PopdownMixin(object):

    def set_popdown(self, selection, entry):
        if not entry.child:  # entry is destroyed
            return
        model, lengths = self.get_popdown_model(selection)
        entry.set_model(model)
        # GTK 2.24 and above use a ComboBox instead of a ComboBoxEntry
        if hasattr(entry, 'set_text_column'):
            entry.set_text_column(0)
        else:
            entry.set_entry_text_column(0)
        completion = gtk.EntryCompletion()
        completion.set_inline_selection(True)
        completion.set_model(model)
        entry.child.set_completion(completion)
        if lengths:
            pop = sorted(lengths, reverse=True)
            average = sum(pop) / len(pop)
            deviation = int(math.sqrt(sum((x - average) ** 2 for x in pop) /
                    len(pop)))
            width = max(next((x for x in pop if x < (deviation * 4)), 10), 10)
        else:
            width = 10
        entry.child.set_width_chars(width)
        if lengths:
            entry.child.set_max_length(max(lengths))
        completion.set_text_column(0)
        completion.connect('match-selected', self.match_selected, entry)

    def get_popdown_model(self, selection):
        model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
        lengths = []
        for (value, name) in selection:
            name = str(name)
            model.append((name, value))
            lengths.append(len(name))
        return model, lengths

    def match_selected(self, completion, model, iter_, entry):
        value, = model.get(iter_, 1)
        model = entry.get_model()
        for i, values in enumerate(model):
            if values[1] == value:
                entry.set_active(i)
                break

    def get_popdown_value(self, entry):
        active = entry.get_active()
        if active < 0:
            return None
        else:
            model = entry.get_model()
            return model[active][1]

    def set_popdown_value(self, entry, value):
        active = -1
        model = entry.get_model()
        for i, selection in enumerate(model):
            if selection[1] == value:
                active = i
                break
        else:
            if value:
                return False
        entry.set_active(active)
        return True
