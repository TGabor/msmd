"""This module implements the abstraction over a given piece
of music."""
from __future__ import print_function

import logging
import os
import shutil

import sys

import time
import yaml

from sheet_manager.data_model.performance import Performance
from sheet_manager.data_model.util import SheetManagerDBError

__version__ = "0.0.1"
__author__ = "Jan Hajic jr."


class Piece(object):
    """This class represents a single piece. The piece with all its
    scores, performances, encodings, etc. lives in the filesystem
    in a directory; this class is just an abstraction to make manipulating
    the piece more comfortable.

    Attributes
    ----------

    * ``name``: a unique identifier of the piece within the collection.
    * ``folder``: the path to the folder of the piece.
    * ``collection_root``: the Piece remembers the collection it is a part of.
    * ``metadata``: a dict of arbitrary descriptors. Expects a ``meta.yml``
      file in the ``piece.folder`` directory.
    * ``encodings``: a dict of the available encoding files. The keys
      are encoding shortcuts (mxml, ly, midi, mei, ...). One of these
      files should always be available. When the piece is initialized,
      one of the available encodings must be selected as the authority
      encoding, from which everything else (scores, performances, ...)
      is derived.
    * ``performances``: a dict of available performances (directories).
      Keys are performance names, values are paths.
    * ``scores``: a dict of available scores (directories). Keys are
      score names, values are paths.

    All paths stored in the attributes include the ``collection_root``
    path. If the root is ``~/baroque`` and there is a piece in the
    collection called ``reichenauer_sonata-1_allegro``, then the path
    stored in ``folder`` will be ``~/baroque/reichenauer_sonata-1_allegro``.
    This implies: if ``collection_root`` is a relative path, all
    the other paths will be relative to the same point in the filesystem
    to which the ``collection_root`` is relative.

    Getting performances and scores
    -------------------------------

    The Piece only stores the paths. In order to load the actual
    ``Performance`` and ``Score`` objects, you need to use the
    ``load_performance()``, ``load_all_performances()`` methods (and
    their ``load_score()`` analogies).

    """
    DEFAULT_META_FNAME = 'meta.yml'
    AVAILABLE_AUTHORITIES = ['mxml', 'ly', 'midi', 'mei']

    def __init__(self, name, root, authority_format='ly'):
        """Initialize the Piece.

        :param root: The root directory of the collection. Contains
            the directories for individual pieces.

        :param piece_name: The directory that contains everything associated
            with the given piece: encodings, scores, performances, etc.

        :param authority_encoding: Each piece is at its core represented
            by the *authority encoding* (term borrowed from librarians).
            This is the "unmovable truth" for the piece; if performances
            or scores are generated automatically for the piece (which is
            usually the case), the sheet manager workflow will be based
            on this value. See ``AVAILABLE_ENCODINGS`` class attribute
            for a list of encodings which it is possible to specify.
        """
        if not os.path.isdir(root):
            raise SheetManagerDBError('Collection root directory does not'
                                      ' exist: {0}'.format(root))

        piece_folder = os.path.join(root, name)
        if not os.path.isdir(piece_folder):
            raise SheetManagerDBError('Piece {0} in collection {1} does'
                                      ' not exist'.format(name, root))

        if authority_format not in self.AVAILABLE_AUTHORITIES:
            raise ValueError('Authority format not supported: {0}'
                             ''.format(authority_format))

        self.name = name
        self.folder = piece_folder
        self.collection_root = root

        self.performance_dir = os.path.join(self.folder, 'performances')
        self.score_dir = os.path.join(self.folder, 'scores')
        self._ensure_piece_structure()

        self.metadata = self.load_metadata()

        self.encodings = self.collect_encodings()
        if authority_format not in self.encodings:
            raise SheetManagerDBError('Piece {0} in collection {1} does'
                                      ' not have the requested authority'
                                      ' encoding {2}. (Available encodings:'
                                      ' {3}'.format(self.name, root,
                                                    authority_format,
                                                    self.encodings.values()))
        self.authority_format = authority_format
        self.authority = self.encodings[authority_format]

        self.performances = self.collect_performances()
        self.scores = self.collect_scores()

    def _ensure_piece_structure(self):
        """Creates the basic expected directory structure."""
        if not os.path.isdir(self.performance_dir):
            os.mkdir(self.performance_dir)
        if not os.path.isdir(self.score_dir):
            os.mkdir(self.score_dir)

    def load_score(self, score_name):
        self.update()
        raise NotImplementedError()

    def load_all_scores(self, score_name):
        raise NotImplementedError()

    def load_performance(self, performance_name):
        """Creates a ``Performance`` object for the given performance
        and returns it."""
        self.update()
        if performance_name not in self.performances:
            raise SheetManagerDBError('Piece {0} in collection {1} does'
                                      ' not have a performance with name {2}.'
                                      ' Available performances: {3}'
                                      ''.format(self.name, self.collection_root,
                                                performance_name,
                                                self.performances.keys()))
        performance_dir = self.performances[performance_name]
        performance = Performance(dir=performance_dir,
                                  piece_name=self.name)
        return performance

    def load_all_performances(self):
        """Returns a list of all the available Performances."""
        return [self.load_performance(p) for p in self.performances]

    def update(self):
        """Refreshes the index of available performances
        and scores."""
        self.encodings = self.collect_encodings()
        self._set_authority(self.authority_format)

        self._ensure_piece_structure()
        self.performances = self.collect_performances()
        self.scores = self.collect_scores()

    def _set_authority(self, authority_format):
        """Sets the authority to the selected format. Don't do this
        unless you are sure what you are doing. If you really need
        to derive something in the piece from different authority
        encodings, consider initializing another ``Piece`` instance."""
        if authority_format not in self.AVAILABLE_AUTHORITIES:
            raise ValueError('Authority format not supported: {0}'
                             ''.format(authority_format))
        if authority_format not in self.encodings:
            raise SheetManagerDBError('Piece {0} in collection {1} does'
                                      ' not have the requested authority'
                                      ' encoding {2}. (Available encodings:'
                                      ' {3}'.format(self.name,
                                                    self.collection_root,
                                                    authority_format,
                                                    self.encodings.values()))
        self.authority_format = authority_format
        self.authority = self.encodings[authority_format]

    def collect_performances(self):
        """Collects a dict of the available performances. Keys
        are performance names (corresponding to directory naes
        in the ``self.performance_dir`` directory), values are
        the paths to these directories."""
        performances = {p: os.path.join(self.performance_dir, p)
                        for p in os.listdir(self.performance_dir)}
        return performances

    def collect_scores(self):
        """Collects a dict of the available scores. Keys
        are score names (corresponding to directory naes
        in the ``self.score_dir`` directory), values are
        the paths to these directories."""
        scores = {s: os.path.join(self.score_dir, s)
                  for s in os.listdir(self.score_dir)}
        return scores

    def collect_encodings(self):
        """Collects various encodings that SheetManager can deal with
        as authority."""
        encodings = dict()

        mxml = os.path.join(self.folder, self.name + '.xml')
        if os.path.isfile(mxml):
            encodings['mxml'] = mxml

        ly = os.path.join(self.folder, self.name + '.ly')
        if os.path.isfile(ly):
            encodings['ly'] = ly

        midi = os.path.join(self.folder, self.name + '.mid')
        if not os.path.isfile(midi):
            midi += 'i'
        if os.path.isfile(midi):
            encodings['midi'] = midi

        mei = os.path.join(self.folder, self.name + '.mei')
        if os.path.isfile(mei):
            encodings['mei'] = mei

        return encodings

    def load_metadata(self):
        """Loads arbitrary YAML descriptors with the default name (meta.yml)."""
        metafile = os.path.join(self.folder, self.DEFAULT_META_FNAME)
        if not os.path.isfile(metafile):
            logging.warn('Piece {0} has no metadata file: {1}'
                         ''.format(self.name, self.DEFAULT_META_FNAME))
            return dict()

        with open(metafile, 'r') as hdl:
            metadata = yaml.load_all(hdl)

        return metadata

    def clear_performances(self):
        """Remove all performances. Use this carefully!"""
        for p in self.performances:
            self.remove_performance(p)

    def remove_performance(self, name):
        """Removes the given performance."""
        self.update()
        if name not in self.performances:
            logging.warn('Piece {0}: trying to remove performance {1},'
                         ' but it does not exist!'.format(self.name, name))
            return

        shutil.rmtree(self.performances[name])
        self.update()

    def add_performance(self, name, audio_file, midi_file=None,
                        overwrite=False):
        """Creates a new performance in the piece from existing audio
        and optionally MIDI files.

        :param name: Name of the new performance. The performance folder
            will have this name, and the performance audio (and midi) file
            names will be derived from this name by simply copying the format
            suffix from the ``audio_file`` and ``midi_file`` arguments.

        :param audio_file: The audio file for the performance. Will be copied
            into the newly created performance directory, with the filename
            derived as the `name`` plus the format suffix. Required.

        :param midi_file: The performance MIDI. Optional. Will be copied
            into the newly created performance directory. Same name convention
            as for ``audio_file``.

        :param overwrite: If true, if a performance with the given ``name``
            exists, will delete it.
        """
        if name in self.performances:
            if overwrite:
                logging.warning('Piece {0}: performance {1} already exists,'
                                ' overwriting!'.format(self.name, name))
                time.sleep(5)
                self.remove_performance(name)
            else:
                raise SheetManagerDBError('Piece {0}: performance {1} already'
                                          ' exists!'.format(self.name, name))
        new_performance_dir = os.path.join(self.performance_dir, name)

        # This part should be refactored as performance.build_performance()
        os.mkdir(new_performance_dir)

        audio_fmt = os.path.splitext(audio_file)[-1]
        perf_audio_filename = os.path.join(new_performance_dir,
                                           name + audio_fmt)
        shutil.copyfile(audio_file, perf_audio_filename)

        if midi_file:
            midi_fmt = os.path.splitext(midi_file)[-1]
            perf_midi_filename = os.path.join(new_performance_dir,
                                              name + midi_fmt)
            shutil.copyfile(midi_file, perf_midi_filename)

        self.update()

        # Test-load the Performance. Ensures folder structure initialization.
        _ = self.load_performance(name)