import collections
import io
import errno
import os
import pathlib
import sys
import shutil
import tempfile
import unittest
from contextlib import contextmanager

from test import support
TESTFN = support.TESTFN


class _BaseFlavourTest(unittest.TestCase):

    def _check_parse_parts(self, arg, expected):
        f = self.flavour.parse_parts
        sep = self.flavour.sep
        altsep = self.flavour.sep
        actual = f([x.replace('/', sep) for x in arg])
        self.assertEqual(actual, expected)
        if altsep:
            actual = f([x.replace('/', altsep) for x in arg])
            self.assertEqual(actual, expected)

    def test_parse_parts_common(self):
        check = self._check_parse_parts
        sep = self.flavour.sep
        # Unanchored parts
        check([],                   ('', '', []))
        check(['a'],                ('', '', ['a']))
        check(['a/'],               ('', '', ['a']))
        check(['a', 'b'],           ('', '', ['a', 'b']))
        # Expansion
        check(['a/b'],              ('', '', ['a', 'b']))
        check(['a/b/'],             ('', '', ['a', 'b']))
        check(['a', 'b/c', 'd'],    ('', '', ['a', 'b', 'c', 'd']))
        # Collapsing and stripping excess slashes
        check(['a', 'b//c', 'd'],   ('', '', ['a', 'b', 'c', 'd']))
        check(['a', 'b/c/', 'd'],   ('', '', ['a', 'b', 'c', 'd']))
        # Eliminating standalone dots
        check(['.'],                ('', '', []))
        check(['.', '.', 'b'],      ('', '', ['b']))
        check(['a', '.', 'b'],      ('', '', ['a', 'b']))
        check(['a', '.', '.'],      ('', '', ['a']))
        # The first part is anchored
        check(['/a/b'],             ('', sep, [sep, 'a', 'b']))
        check(['/a', 'b'],          ('', sep, [sep, 'a', 'b']))
        check(['/a/', 'b'],         ('', sep, [sep, 'a', 'b']))
        # Ignoring parts before an anchored part
        check(['a', '/b', 'c'],     ('', sep, [sep, 'b', 'c']))
        check(['a', '/b', '/c'],    ('', sep, [sep, 'c']))


class PosixFlavourTest(_BaseFlavourTest):
    flavour = pathlib._posix_flavour

    def test_parse_parts(self):
        check = self._check_parse_parts
        # Paths which look like NT paths aren't treated specially
        check(['c:a'],                  ('', '', ['c:a']))
        check(['c:\\a'],                ('', '', ['c:\\a']))
        check(['\\a'],                  ('', '', ['\\a']))

    def test_splitroot(self):
        f = self.flavour.splitroot
        self.assertEqual(f(''), ('', '', ''))
        self.assertEqual(f('a'), ('', '', 'a'))
        self.assertEqual(f('a/b'), ('', '', 'a/b'))
        self.assertEqual(f('a/b/'), ('', '', 'a/b/'))
        self.assertEqual(f('/a'), ('', '/', 'a'))
        self.assertEqual(f('/a/b'), ('', '/', 'a/b'))
        self.assertEqual(f('/a/b/'), ('', '/', 'a/b/'))
        # The root is collapsed when there are redundant slashes
        self.assertEqual(f('//a'), ('', '/', 'a'))
        self.assertEqual(f('///a/b'), ('', '/', 'a/b'))
        # Paths which look like NT paths aren't treated specially
        self.assertEqual(f('c:/a/b'), ('', '', 'c:/a/b'))
        self.assertEqual(f('\\/a/b'), ('', '', '\\/a/b'))
        self.assertEqual(f('\\a\\b'), ('', '', '\\a\\b'))


class NTFlavourTest(_BaseFlavourTest):
    flavour = pathlib._nt_flavour

    def test_parse_parts(self):
        check = self._check_parse_parts
        # First part is anchored
        check(['c:'],                   ('c:', '', ['c:']))
        check(['c:\\'],                 ('c:', '\\', ['c:\\']))
        check(['\\'],                   ('', '\\', ['\\']))
        check(['c:a'],                  ('c:', '', ['c:', 'a']))
        check(['c:\\a'],                ('c:', '\\', ['c:\\', 'a']))
        check(['\\a'],                  ('', '\\', ['\\', 'a']))
        # UNC paths
        check(['\\\\a\\b'],             ('\\\\a\\b', '\\', ['\\\\a\\b\\']))
        check(['\\\\a\\b\\'],           ('\\\\a\\b', '\\', ['\\\\a\\b\\']))
        check(['\\\\a\\b\\c'],          ('\\\\a\\b', '\\', ['\\\\a\\b\\', 'c']))
        # Second part is anchored, so that the first part is ignored
        check(['a', 'Z:b', 'c'],        ('Z:', '', ['Z:', 'b', 'c']))
        check(['a', 'Z:\\b', 'c'],      ('Z:', '\\', ['Z:\\', 'b', 'c']))
        check(['a', '\\b', 'c'],        ('', '\\', ['\\', 'b', 'c']))
        # UNC paths
        check(['a', '\\\\b\\c', 'd'],   ('\\\\b\\c', '\\', ['\\\\b\\c\\', 'd']))
        # Collapsing and stripping excess slashes
        check(['a', 'Z:\\\\b\\\\c\\', 'd\\'], ('Z:', '\\', ['Z:\\', 'b', 'c', 'd']))
        # UNC paths
        check(['a', '\\\\b\\c\\\\', 'd'], ('\\\\b\\c', '\\', ['\\\\b\\c\\', 'd']))

    def test_splitroot(self):
        f = self.flavour.splitroot
        self.assertEqual(f(''), ('', '', ''))
        self.assertEqual(f('a'), ('', '', 'a'))
        self.assertEqual(f('a\\b'), ('', '', 'a\\b'))
        self.assertEqual(f('\\a'), ('', '\\', 'a'))
        self.assertEqual(f('\\a\\b'), ('', '\\', 'a\\b'))
        self.assertEqual(f('c:a\\b'), ('c:', '', 'a\\b'))
        self.assertEqual(f('c:\\a\\b'), ('c:', '\\', 'a\\b'))
        # Redundant slashes in the root are collapsed
        self.assertEqual(f('\\\\a'), ('', '\\', 'a'))
        self.assertEqual(f('\\\\\\a/b'), ('', '\\', 'a/b'))
        self.assertEqual(f('c:\\\\a'), ('c:', '\\', 'a'))
        self.assertEqual(f('c:\\\\\\a/b'), ('c:', '\\', 'a/b'))
        # Valid UNC paths
        self.assertEqual(f('\\\\a\\b'), ('\\\\a\\b', '\\', ''))
        self.assertEqual(f('\\\\a\\b\\'), ('\\\\a\\b', '\\', ''))
        self.assertEqual(f('\\\\a\\b\\c\\d'), ('\\\\a\\b', '\\', 'c\\d'))
        # These are non-UNC paths (according to ntpath.py and test_ntpath)
        # However, command.com says such paths are invalid, so it's
        # difficult to know what the right semantics are
        self.assertEqual(f('\\\\\\a\\b'), ('', '\\', 'a\\b'))
        self.assertEqual(f('\\\\a'), ('', '\\', 'a'))


#
# Tests for the pure classes
#

class _BasePurePathTest(unittest.TestCase):

    # keys are canonical paths, values are list of tuples of arguments
    # supposed to produce equal paths
    equivalences = {
        'a/b': [
            ('a', 'b'), ('a/', 'b'), ('a', 'b/'), ('a/', 'b/'),
            ('a/b/',), ('a//b',), ('a//b//',),
            # empty components get removed
            ('', 'a', 'b'), ('a', '', 'b'), ('a', 'b', ''),
            ],
        '/b/c/d': [
            ('a', '/b/c', 'd'), ('a', '//b//c', 'd/'),
            ('/a', '/b/c', 'd'),
            # empty components get removed
            ('/', 'b', '', 'c/d'), ('/', '', 'b/c/d'), ('', '/b/c/d'),
            ],
    }

    def setUp(self):
        p = self.cls('a')
        self.flavour = p._flavour
        self.sep = self.flavour.sep
        self.altsep = self.flavour.altsep

    def test_constructor_common(self):
        P = self.cls
        p = P('a')
        self.assertIsInstance(p, P)
        P('a', 'b', 'c')
        P('/a', 'b', 'c')
        P('a/b/c')
        P('/a/b/c')
        self.assertEqual(P(P('a')), P('a'))
        self.assertEqual(P(P('a'), 'b'), P('a/b'))
        self.assertEqual(P(P('a'), P('b')), P('a/b'))

    def test_join_common(self):
        P = self.cls
        p = P('a/b')
        pp = p.join('c')
        self.assertEqual(pp, P('a/b/c'))
        self.assertIs(type(pp), type(p))
        pp = p.join('c', 'd')
        self.assertEqual(pp, P('a/b/c/d'))
        pp = p.join(P('c'))
        self.assertEqual(pp, P('a/b/c'))
        pp = p.join('/c')
        self.assertEqual(pp, P('/c'))

    def test_getitem_common(self):
        # Basically the same as join()
        P = self.cls
        p = P('a/b')
        pp = p['c']
        self.assertEqual(pp, P('a/b/c'))
        self.assertIs(type(pp), type(p))
        pp = p['c', 'd']
        self.assertEqual(pp, P('a/b/c/d'))
        pp = p[P('c')]
        self.assertEqual(pp, P('a/b/c'))
        pp = p['/c']
        self.assertEqual(pp, P('/c'))

    def _check_str(self, expected, args):
        p = self.cls(*args)
        self.assertEqual(str(p), expected.replace('/', self.sep))

    def test_str_common(self):
        # Canonicalized paths roundtrip
        for pathstr in ('a', 'a/b', 'a/b/c', '/', '/a/b', '/a/b/c'):
            self._check_str(pathstr, (pathstr,))
        # Special case for the empty path
        self._check_str('.', ('',))
        # Other tests for str() are in test_equivalences()

    def test_as_posix_common(self):
        P = self.cls
        for pathstr in ('a', 'a/b', 'a/b/c', '/', '/a/b', '/a/b/c'):
            self.assertEqual(P(pathstr).as_posix(), pathstr)
        # Other tests for as_posix() are in test_equivalences()

    def test_as_bytes_common(self):
        P = self.cls
        sep = os.fsencode(self.sep)
        self.assertEqual(P('a/b').as_bytes(), b'a' + sep + b'b')
        self.assertEqual(bytes(P('a/b')), b'a' + sep + b'b')

    def test_repr_common(self):
        for pathstr in ('a', 'a/b', 'a/b/c', '/', '/a/b', '/a/b/c'):
            p = self.cls(pathstr)
            clsname = p.__class__.__name__
            r = repr(p)
            # The repr() is in the form ClassName("canonical path")
            self.assertTrue(r.startswith(clsname + '('), r)
            self.assertTrue(r.endswith(')'), r)
            inner = r[len(clsname) + 1 : -1]
            self.assertEqual(eval(inner), str(p))

    def test_eq_common(self):
        P = self.cls
        self.assertEqual(P('a/b'), P('a/b'))
        self.assertEqual(P('a/b'), P('a', 'b'))
        self.assertNotEqual(P('a/b'), P('a'))
        self.assertNotEqual(P('a/b'), P('/a/b'))
        self.assertNotEqual(P('a/b'), P())
        self.assertNotEqual(P('/a/b'), P('/'))
        self.assertNotEqual(P(), P('/'))

    def test_ordering_common(self):
        # Ordering is tuple-alike
        def assertLess(a, b):
            self.assertLess(a, b)
            self.assertGreater(b, a)
        P = self.cls
        a = P('a')
        b = P('a/b')
        c = P('abc')
        d = P('b')
        assertLess(a, b)
        assertLess(a, c)
        assertLess(a, d)
        assertLess(b, c)
        assertLess(c, d)
        P = self.cls
        a = P('/a')
        b = P('/a/b')
        c = P('/abc')
        d = P('/b')
        assertLess(a, b)
        assertLess(a, c)
        assertLess(a, d)
        assertLess(b, c)
        assertLess(c, d)

    def test_parts_common(self):
        sep = self.sep
        P = self.cls
        p = P('a/b')
        parts = p.parts
        # The object gets reused
        self.assertIs(parts, p.parts)
        # Sequence protocol
        self.assertIsInstance(parts, collections.Sequence)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], 'a')
        self.assertEqual(list(parts), ['a', 'b'])
        self.assertEqual(parts[:], P('a/b'))
        self.assertEqual(parts[0:1], P('a'))
        p = P('/a/b')
        parts = p.parts
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], sep)
        self.assertEqual(list(parts), [sep, 'a', 'b'])
        self.assertEqual(parts[:], P('/a/b'))
        self.assertEqual(parts[:2], P('/a'))
        self.assertEqual(parts[1:], P('a/b'))

    def test_equivalences(self):
        for k, tuples in self.equivalences.items():
            canon = k.replace('/', self.sep)
            posix = k.replace(self.sep, '/')
            if canon != posix:
                tuples = tuples + [
                    tuple(part.replace('/', self.sep) for part in t)
                    for t in tuples
                    ]
                tuples.append((posix, ))
            pcanon = self.cls(canon)
            for t in tuples:
                p = self.cls(*t)
                self.assertEqual(p, pcanon, "failed with args {}".format(t))
                self.assertEqual(hash(p), hash(pcanon))
                self.assertEqual(str(p), canon)
                self.assertEqual(p.as_posix(), posix)

    def test_parent_common(self):
        # Relative
        P = self.cls
        p = P('a/b/c')
        self.assertEqual(p.parent(), P('a/b'))
        self.assertEqual(p.parent(2), P('a'))
        self.assertEqual(p.parent(3), P())
        self.assertEqual(p.parent(4), P())
        # Anchored
        p = P('/a/b/c')
        self.assertEqual(p.parent(), P('/a/b'))
        self.assertEqual(p.parent(2), P('/a'))
        self.assertEqual(p.parent(3), P('/'))
        self.assertEqual(p.parent(4), P('/'))

    def test_parents_common(self):
        # Relative
        P = self.cls
        p = P('a/b/c')
        it = p.parents()
        self.assertEqual(next(it), P('a/b'))
        self.assertEqual(list(it), [P('a'), P()])
        # Anchored
        p = P('/a/b/c')
        it = p.parents()
        self.assertEqual(next(it), P('/a/b'))
        self.assertEqual(list(it), [P('/a'), P('/')])

    def test_drive_common(self):
        P = self.cls
        self.assertEqual(P('a/b').drive, '')
        self.assertEqual(P('/a/b').drive, '')
        self.assertEqual(P('').drive, '')

    def test_root_common(self):
        P = self.cls
        sep = self.sep
        self.assertEqual(P('').root, '')
        self.assertEqual(P('a/b').root, '')
        self.assertEqual(P('/').root, sep)
        self.assertEqual(P('/a/b').root, sep)

    def test_ext_common(self):
        P = self.cls
        self.assertEqual(P('').ext, '')
        self.assertEqual(P('.').ext, '')
        self.assertEqual(P('/').ext, '')
        self.assertEqual(P('a/b').ext, '')
        self.assertEqual(P('/a/b').ext, '')
        self.assertEqual(P('/a/b/.').ext, '')
        self.assertEqual(P('a/b.py').ext, '.py')
        self.assertEqual(P('/a/b.py').ext, '.py')
        self.assertEqual(P('a/b.tar.gz').ext, '.tar.gz')
        self.assertEqual(P('/a/b.tar.gz').ext, '.tar.gz')

    def test_relative_common(self):
        P = self.cls
        p = P('a/b')
        self.assertEqual(p.relative(), P('a/b'))
        p = P('/a/b')
        self.assertEqual(p.relative(), P('a/b'))
        p = P('/')
        self.assertEqual(p.relative(), P())

    def test_relative_to_common(self):
        P = self.cls
        p = P('a/b')
        self.assertRaises(TypeError, p.relative_to)
        self.assertEqual(p.relative_to(P()), P('a/b'))
        self.assertEqual(p.relative_to(P('a')), P('b'))
        self.assertEqual(p.relative_to(P('a/b')), P())
        # With several args
        self.assertEqual(p.relative_to('a', 'b'), P())
        # Unrelated paths
        self.assertRaises(ValueError, p.relative_to, P('c'))
        self.assertRaises(ValueError, p.relative_to, P('a/b/c'))
        self.assertRaises(ValueError, p.relative_to, P('a/c'))
        self.assertRaises(ValueError, p.relative_to, P('/a'))
        p = P('/a/b')
        self.assertEqual(p.relative_to(P('/')), P('a/b'))
        self.assertEqual(p.relative_to(P('/a')), P('b'))
        self.assertEqual(p.relative_to(P('/a/b')), P())
        # Unrelated paths
        self.assertRaises(ValueError, p.relative_to, P('/c'))
        self.assertRaises(ValueError, p.relative_to, P('/a/b/c'))
        self.assertRaises(ValueError, p.relative_to, P('/a/c'))
        self.assertRaises(ValueError, p.relative_to, P())
        self.assertRaises(ValueError, p.relative_to, P('a'))


class PurePosixPathTest(_BasePurePathTest):
    cls = pathlib.PurePosixPath

    def test_root(self):
        P = self.cls
        # This is an UNC path under Windows
        self.assertEqual(P('//a/b').root, '/')

    def test_eq(self):
        P = self.cls
        self.assertNotEqual(P('a/b'), P('A/b'))

    def test_is_absolute(self):
        P = self.cls
        self.assertFalse(P().is_absolute())
        self.assertFalse(P('a').is_absolute())
        self.assertFalse(P('a/b/').is_absolute())
        self.assertTrue(P('/').is_absolute())
        self.assertTrue(P('/a').is_absolute())
        self.assertTrue(P('/a/b/').is_absolute())

    def test_normcase(self):
        P = self.cls
        p = P('/Aa/Bb/Cc').normcase()
        self.assertEqual(P('/Aa/Bb/Cc'), p)
        self.assertEqual('/Aa/Bb/Cc', str(p))

    def test_is_reserved(self):
        P = self.cls
        self.assertIs(False, P('').is_reserved())
        self.assertIs(False, P('/').is_reserved())
        self.assertIs(False, P('/foo/bar').is_reserved())
        self.assertIs(False, P('/dev/con/PRN/NUL').is_reserved())


class PureNTPathTest(_BasePurePathTest):
    cls = pathlib.PureNTPath

    equivalences = _BasePurePathTest.equivalences.copy()
    equivalences.update({
        'c:a': [ ('c:', 'a'), ('c:', 'a/'), ('/', 'c:', 'a') ],
        'c:/a': [
            ('c:/', 'a'), ('c:', '/', 'a'), ('c:', '/a'),
            ('/z', 'c:/', 'a'), ('//x/y', 'c:/', 'a'),
            ],
        '//a/b/': [ ('//a/b',) ],
        '//a/b/c': [
            ('//a/b', 'c'), ('//a/b/', 'c'),
            ],
    })

    def test_str(self):
        p = self.cls('a/b/c')
        self.assertEqual(str(p), 'a\\b\\c')
        p = self.cls('c:/a/b/c')
        self.assertEqual(str(p), 'c:\\a\\b\\c')
        p = self.cls('//a/b')
        self.assertEqual(str(p), '\\\\a\\b\\')
        p = self.cls('//a/b/c')
        self.assertEqual(str(p), '\\\\a\\b\\c')
        p = self.cls('//a/b/c/d')
        self.assertEqual(str(p), '\\\\a\\b\\c\\d')

    def test_eq(self):
        P = self.cls
        self.assertEqual(P('c:a/b'), P('c:a/b'))
        self.assertEqual(P('c:a/b'), P('c:', 'a', 'b'))
        self.assertNotEqual(P('c:a/b'), P('d:a/b'))
        self.assertNotEqual(P('c:a/b'), P('c:/a/b'))
        self.assertNotEqual(P('/a/b'), P('c:/a/b'))
        # Case-insensitivity
        self.assertEqual(P('a/B'), P('A/b'))
        self.assertEqual(P('C:a/B'), P('c:A/b'))
        self.assertEqual(P('//Some/SHARE/a/B'), P('//somE/share/A/b'))

    def test_ordering_common(self):
        # Case-insensitivity
        def assertOrderedEqual(a, b):
            self.assertLessEqual(a, b)
            self.assertGreaterEqual(b, a)
        P = self.cls
        p = P('c:A/b')
        q = P('C:a/B')
        assertOrderedEqual(p, q)
        self.assertFalse(p < q)
        self.assertFalse(p > q)
        p = P('//some/Share/A/b')
        q = P('//Some/SHARE/a/B')
        assertOrderedEqual(p, q)
        self.assertFalse(p < q)
        self.assertFalse(p > q)

    def test_parts(self):
        P = self.cls
        p = P('c:a/b')
        parts = p.parts
        self.assertEqual(len(parts), 3)
        self.assertEqual(list(parts), ['c:', 'a', 'b'])
        self.assertEqual(parts[:2], P('c:a'))
        self.assertEqual(parts[1:], P('a/b'))
        p = P('c:/a/b')
        parts = p.parts
        self.assertEqual(len(parts), 3)
        self.assertEqual(list(parts), ['c:\\', 'a', 'b'])
        self.assertEqual(parts[:2], P('c:/a'))
        self.assertEqual(parts[1:], P('a/b'))
        p = P('//a/b/c/d')
        parts = p.parts
        self.assertEqual(len(parts), 3)
        self.assertEqual(list(parts), ['\\\\a\\b\\', 'c', 'd'])
        self.assertEqual(parts[:2], P('//a/b/c'))
        self.assertEqual(parts[1:], P('c/d'))

    def test_parent(self):
        # Anchored
        P = self.cls
        p = P('z:a/b/c')
        self.assertEqual(p.parent(), P('z:a/b'))
        self.assertEqual(p.parent(2), P('z:a'))
        self.assertEqual(p.parent(3), P('z:'))
        self.assertEqual(p.parent(4), P('z:'))
        p = P('z:/a/b/c')
        self.assertEqual(p.parent(), P('z:/a/b'))
        self.assertEqual(p.parent(2), P('z:/a'))
        self.assertEqual(p.parent(3), P('z:/'))
        self.assertEqual(p.parent(4), P('z:/'))
        p = P('//a/b/c/d')
        self.assertEqual(p.parent(), P('//a/b/c'))
        self.assertEqual(p.parent(2), P('//a/b'))
        self.assertEqual(p.parent(3), P('//a/b'))

    def test_parents(self):
        # Anchored
        P = self.cls
        p = P('z:a/b/')
        self.assertEqual(list(p.parents()), [P('z:a'), P('z:')])
        p = P('z:/a/b/')
        self.assertEqual(list(p.parents()), [P('z:/a'), P('z:/')])
        p = P('//a/b/c/d')
        self.assertEqual(list(p.parents()), [P('//a/b/c'), P('//a/b')])

    def test_drive(self):
        P = self.cls
        self.assertEqual(P('c:').drive, 'c:')
        self.assertEqual(P('c:a/b').drive, 'c:')
        self.assertEqual(P('c:/').drive, 'c:')
        self.assertEqual(P('c:/a/b/').drive, 'c:')
        self.assertEqual(P('//a/b').drive, '\\\\a\\b')
        self.assertEqual(P('//a/b/').drive, '\\\\a\\b')
        self.assertEqual(P('//a/b/c/d').drive, '\\\\a\\b')

    def test_root(self):
        P = self.cls
        self.assertEqual(P('c:').root, '')
        self.assertEqual(P('c:a/b').root, '')
        self.assertEqual(P('c:/').root, '\\')
        self.assertEqual(P('c:/a/b/').root, '\\')
        self.assertEqual(P('//a/b').root, '\\')
        self.assertEqual(P('//a/b/').root, '\\')
        self.assertEqual(P('//a/b/c/d').root, '\\')

    def test_ext(self):
        P = self.cls
        self.assertEqual(P('c:').ext, '')
        self.assertEqual(P('c:/').ext, '')
        self.assertEqual(P('c:a/b').ext, '')
        self.assertEqual(P('c:/a/b').ext, '')
        self.assertEqual(P('c:a/b.py').ext, '.py')
        self.assertEqual(P('c:/a/b.py').ext, '.py')
        self.assertEqual(P('c:a/b.tar.gz').ext, '.tar.gz')
        self.assertEqual(P('c:/a/b.tar.gz').ext, '.tar.gz')
        self.assertEqual(P('//My.py/Share.php').ext, '')
        self.assertEqual(P('//My.py/Share.php/a/b').ext, '')

    def test_relative(self):
        P = self.cls
        p = P('c:a/b')
        self.assertEqual(p.relative(), P('a/b'))
        p = P('c:/a/b')
        self.assertEqual(p.relative(), P('a/b'))
        p = P('c:')
        self.assertEqual(p.relative(), P())
        p = P('c:/')
        self.assertEqual(p.relative(), P())

    def test_relative_to(self):
        P = self.cls
        p = P('c:a/b')
        self.assertEqual(p.relative_to(P('c:')), P('a/b'))
        self.assertEqual(p.relative_to(P('c:a')), P('b'))
        self.assertEqual(p.relative_to(P('c:a/b')), P())
        # Unrelated paths
        self.assertRaises(ValueError, p.relative_to, P())
        self.assertRaises(ValueError, p.relative_to, P('d:'))
        self.assertRaises(ValueError, p.relative_to, P('a'))
        self.assertRaises(ValueError, p.relative_to, P('/a'))
        self.assertRaises(ValueError, p.relative_to, P('c:a/b/c'))
        self.assertRaises(ValueError, p.relative_to, P('c:a/c'))
        self.assertRaises(ValueError, p.relative_to, P('c:/a'))
        p = P('c:/a/b')
        self.assertEqual(p.relative_to(P('c:')), P('/a/b'))
        self.assertEqual(p.relative_to(P('c:/')), P('a/b'))
        self.assertEqual(p.relative_to(P('c:/a')), P('b'))
        self.assertEqual(p.relative_to(P('c:/a/b')), P())
        # Unrelated paths
        self.assertRaises(ValueError, p.relative_to, P('c:/c'))
        self.assertRaises(ValueError, p.relative_to, P('c:/a/b/c'))
        self.assertRaises(ValueError, p.relative_to, P('c:/a/c'))
        self.assertRaises(ValueError, p.relative_to, P('c:a'))
        self.assertRaises(ValueError, p.relative_to, P('d:'))
        self.assertRaises(ValueError, p.relative_to, P('d:/'))
        self.assertRaises(ValueError, p.relative_to, P('/a'))
        self.assertRaises(ValueError, p.relative_to, P('//c/a'))
        # UNC paths
        p = P('//a/b/c/d')
        self.assertEqual(p.relative_to(P('//a/b')), P('c/d'))
        self.assertEqual(p.relative_to(P('//a/b/c')), P('d'))
        self.assertEqual(p.relative_to(P('//a/b/c/d')), P())
        # Unrelated paths
        self.assertRaises(ValueError, p.relative_to, P('/a/b/c'))
        self.assertRaises(ValueError, p.relative_to, P('c:/a/b/c'))
        self.assertRaises(ValueError, p.relative_to, P('//z/b/c'))
        self.assertRaises(ValueError, p.relative_to, P('//a/z/c'))

    def test_is_absolute(self):
        P = self.cls
        # Under NT, only paths with both a drive and a root are absolute
        self.assertFalse(P().is_absolute())
        self.assertFalse(P('a').is_absolute())
        self.assertFalse(P('a/b/').is_absolute())
        self.assertFalse(P('/').is_absolute())
        self.assertFalse(P('/a').is_absolute())
        self.assertFalse(P('/a/b/').is_absolute())
        self.assertFalse(P('c:').is_absolute())
        self.assertFalse(P('c:a').is_absolute())
        self.assertFalse(P('c:a/b/').is_absolute())
        self.assertTrue(P('c:/').is_absolute())
        self.assertTrue(P('c:/a').is_absolute())
        self.assertTrue(P('c:/a/b/').is_absolute())
        # UNC paths are absolute by definition
        self.assertTrue(P('//a/b').is_absolute())
        self.assertTrue(P('//a/b/').is_absolute())
        self.assertTrue(P('//a/b/c').is_absolute())
        self.assertTrue(P('//a/b/c/d').is_absolute())

    def test_normcase(self):
        P = self.cls
        p = P('D:/Aa/Bb/Cc').normcase()
        self.assertEqual(P('d:/aa/bb/cc'), p)
        self.assertEqual(r'd:\aa\bb\cc', str(p))

    def test_is_reserved(self):
        P = self.cls
        self.assertIs(False, P('').is_reserved())
        self.assertIs(False, P('/').is_reserved())
        self.assertIs(False, P('/foo/bar').is_reserved())
        self.assertIs(True, P('con').is_reserved())
        self.assertIs(True, P('NUL').is_reserved())
        self.assertIs(True, P('NUL.txt').is_reserved())
        self.assertIs(True, P('com1').is_reserved())
        self.assertIs(True, P('com9.bar').is_reserved())
        self.assertIs(False, P('bar.com9').is_reserved())
        self.assertIs(True, P('lpt1').is_reserved())
        self.assertIs(True, P('lpt9.bar').is_reserved())
        self.assertIs(False, P('bar.lpt9').is_reserved())
        # Only the last component matters
        self.assertIs(False, P('c:/NUL/con/baz').is_reserved())
        # UNC paths are never reserved
        self.assertIs(False, P('//my/share/nul/con/aux').is_reserved())


class PurePathTest(_BasePurePathTest):
    cls = pathlib.PurePath

    def test_concrete_class(self):
        p = self.cls('a')
        self.assertIs(type(p),
            pathlib.PureNTPath if os.name == 'nt' else pathlib.PurePosixPath)

    def test_different_flavours_unequal(self):
        p = pathlib.PurePosixPath('a')
        q = pathlib.PureNTPath('a')
        self.assertNotEqual(p, q)

    def test_different_flavours_unordered(self):
        p = pathlib.PurePosixPath('a')
        q = pathlib.PureNTPath('a')
        with self.assertRaises(TypeError):
            p < q
        with self.assertRaises(TypeError):
            p <= q
        with self.assertRaises(TypeError):
            p > q
        with self.assertRaises(TypeError):
            p >= q


#
# Tests for the concrete classes
#

# Make sure any symbolic links in the base test path are resolved
BASE = os.path.realpath(TESTFN)
join = lambda *x: os.path.join(BASE, *x)
rel_join = lambda *x: os.path.join(TESTFN, *x)

def symlink_skip_reason():
    if not pathlib.supports_symlinks:
        return "no system support for symlinks"
    try:
        os.symlink(__file__, BASE)
    except OSError as e:
        return str(e)
    else:
        support.unlink(BASE)
    return None

symlink_skip_reason = symlink_skip_reason()

only_nt = unittest.skipIf(os.name != 'nt',
                          'test requires a Windows-compatible system')
only_posix = unittest.skipIf(os.name == 'nt',
                             'test requires a POSIX-compatible system')
with_symlinks = unittest.skipIf(symlink_skip_reason, symlink_skip_reason)


@only_posix
class PosixPathAsPureTest(PurePosixPathTest):
    cls = pathlib.PosixPath

@only_nt
class NTPathAsPureTest(PureNTPathTest):
    cls = pathlib.NTPath


class _BasePathTest(unittest.TestCase):
    """Tests for the FS-accessing functionalities of the Path classes."""

    def setUp(self):
        os.mkdir(BASE)
        self.addCleanup(support.rmtree, BASE)
        os.mkdir(join('dirA'))
        os.mkdir(join('dirB'))
        with open(join('fileA'), 'w') as f:
            f.write("this is file A\n")
        with open(join('dirB', 'fileB'), 'w') as f:
            f.write("this is file B\n")
        if not symlink_skip_reason:
            if os.name == 'nt':
                # Workaround for http://bugs.python.org/issue13772
                def dirlink(src, dest):
                    os.symlink(src, dest, target_is_directory=True)
            else:
                def dirlink(src, dest):
                    os.symlink(src, dest)
            # Relative symlinks
            os.symlink('fileA', join('linkA'))
            dirlink('dirB', join('linkB'))
            dirlink(os.path.join('..', 'dirB'), join('dirA', 'linkC'))
            # This one goes upwards but doesn't create a loop
            dirlink(os.path.join('..', 'dirB'), join('dirB', 'linkD'))

    def assertSame(self, path_a, path_b):
        self.assertTrue(os.path.samefile(str(path_a), str(path_b)),
                        "%r and %r don't point to the same file" %
                        (path_a, path_b))

    def assertFileNotFound(self, func, *args, **kwargs):
        exc = FileNotFoundError if sys.version_info >= (3, 3) else EnvironmentError
        with self.assertRaises(exc) as cm:
            func(*args, **kwargs)
        self.assertEqual(cm.exception.errno, errno.ENOENT)

    def _test_cwd(self, p):
        q = self.cls(os.getcwd())
        self.assertEqual(p, q)
        self.assertEqual(str(p), str(q))
        self.assertIs(type(p), type(q))
        self.assertTrue(p.is_absolute())

    def test_cwd(self):
        p = self.cls.cwd()
        self._test_cwd(p)

    def test_empty_path(self):
        # The empty path points to '.'
        p = self.cls('')
        self.assertEqual(p.stat(), os.stat('.'))

    def test_exists(self):
        P = self.cls
        p = P(BASE)
        self.assertIs(True, p.exists())
        self.assertIs(True, p['dirA'].exists())
        self.assertIs(True, p['fileA'].exists())
        self.assertIs(True, p['linkA'].exists())
        self.assertIs(True, p['linkB'].exists())
        self.assertIs(False, p['foo'].exists())
        self.assertIs(False, P('/xyzzy').exists())

    def test_open(self):
        p = self.cls(BASE)
        with p['fileA'].open('r') as f:
            self.assertIsInstance(f, io.TextIOBase)
            self.assertEqual(f.read(), "this is file A\n")
        with p['fileA'].open('rb') as f:
            self.assertIsInstance(f, io.BufferedIOBase)
            self.assertEqual(f.read().strip(), b"this is file A")
        with p['fileA'].open('rb', buffering=0) as f:
            self.assertIsInstance(f, io.RawIOBase)
            self.assertEqual(f.read().strip(), b"this is file A")

    def test_iter(self):
        P = self.cls
        p = P(BASE)
        self.assertIsInstance(p, collections.Iterable)
        it = iter(p)
        paths = set(it)
        expected = ['dirA', 'dirB', 'fileA']
        if not symlink_skip_reason:
            expected += ['linkA', 'linkB']
        self.assertEqual(paths, { P(BASE, q) for q in expected })

    @with_symlinks
    def test_iter_symlink(self):
        # __iter__ on a symlink to a directory
        P = self.cls
        p = P(BASE, 'linkB')
        paths = set(p)
        expected = { P(BASE, 'linkB', q) for q in ['fileB', 'linkD'] }
        self.assertEqual(paths, expected)

    def test_iter_nodir(self):
        # __iter__ on something that is not a directory
        p = self.cls(BASE, 'fileA')
        with self.assertRaises(OSError) as cm:
            list(p)
        # ENOENT or EINVAL under Windows, ENOTDIR otherwise
        # (see issue #12802)
        self.assertIn(cm.exception.errno, (errno.ENOTDIR,
                                           errno.ENOENT, errno.EINVAL))

    def _check_resolve_relative(self, p, expected):
        q = p.resolve()
        self.assertEqual(q, expected)

    def _check_resolve_absolute(self, p, expected):
        q = p.resolve()
        self.assertEqual(q, expected)

    @with_symlinks
    def test_resolve_common(self):
        P = self.cls
        p = P(BASE, 'foo')
        with self.assertRaises(OSError) as cm:
            p.resolve()
        self.assertEqual(cm.exception.errno, errno.ENOENT)
        # These are all relative symlinks
        p = P(BASE, 'dirB', 'fileB')
        self._check_resolve_relative(p, p)
        p = P(BASE, 'linkA')
        self._check_resolve_relative(p, P(BASE, 'fileA'))
        p = P(BASE, 'dirA', 'linkC', 'fileB')
        self._check_resolve_relative(p, P(BASE, 'dirB', 'fileB'))
        p = P(BASE, 'dirB', 'linkD', 'fileB')
        self._check_resolve_relative(p, P(BASE, 'dirB', 'fileB'))
        # Now create absolute symlinks
        with tempfile.TemporaryDirectory(suffix='-dirD') as d:
            os.symlink(os.path.join(d), join('dirA', 'linkX'))
            os.symlink(join('dirB'), os.path.join(d, 'linkY'))
            p = P(BASE, 'dirA', 'linkX', 'linkY', 'fileB')
            self._check_resolve_absolute(p, P(BASE, 'dirB', 'fileB'))

    def test_with(self):
        p = self.cls(BASE)
        it = iter(p)
        it2 = iter(p)
        next(it2)
        with p:
            pass
        # I/O operation on closed path
        self.assertRaises(ValueError, next, it)
        self.assertRaises(ValueError, next, it2)
        self.assertRaises(ValueError, p.open)
        self.assertRaises(ValueError, p.raw_open, os.O_RDONLY)
        self.assertRaises(ValueError, p.resolve)
        self.assertRaises(ValueError, p.abspath)
        self.assertRaises(ValueError, p.__enter__)

    def test_chmod(self):
        p = self.cls(BASE)['fileA']
        mode = p.stat().st_mode
        # Clear writable bit
        new_mode = mode & ~0o222
        p.chmod(new_mode)
        self.assertEqual(p.restat().st_mode, new_mode)
        # Set writable bit
        new_mode = mode | 0o222
        p.chmod(new_mode)
        self.assertEqual(p.restat().st_mode, new_mode)

    # XXX also need a test for lchmod

    def test_stat(self):
        # NOTE: this notation helps trigger openat()-specific behaviour
        # (first opens the parent dir and then the file using the dir fd)
        p = self.cls(BASE)['fileA']
        st = p.stat()
        self.assertEqual(p.stat(), st)
        self.assertEqual(p.restat(), st)
        # Change file mode by flipping write bit
        p.chmod(st.st_mode ^ 0o222)
        self.addCleanup(p.chmod, st.st_mode)
        # Cached value didn't change
        self.assertEqual(p.stat(), st)
        # restat() invalidates the cache
        self.assertNotEqual(p.restat(), st)
        self.assertNotEqual(p.stat(), st)

    @with_symlinks
    def test_lstat(self):
        p = self.cls(BASE)['linkA']
        st = p.stat()
        self.assertNotEqual(st, p.lstat())

    def test_lstat_nosymlink(self):
        p = self.cls(BASE)['fileA']
        st = p.stat()
        self.assertEqual(st, p.lstat())

    def test_unlink(self):
        p = self.cls(BASE)['fileA']
        p.unlink()
        self.assertFileNotFound(p.restat)
        self.assertFileNotFound(p.unlink)

    def test_rmdir(self):
        p = self.cls(BASE)['dirA']
        for q in p:
            q.unlink()
        p.rmdir()
        self.assertFileNotFound(p.restat)
        self.assertFileNotFound(p.unlink)

    def test_rename(self):
        # XXX make sure it overwrites also on Windows?
        P = self.cls(BASE)
        p = P['fileA']
        size = p.stat().st_size
        # Renaming to another path
        q = P['dirA', 'fileAA']
        p.rename(q)
        self.assertEqual(q.stat().st_size, size)
        self.assertFileNotFound(p.restat)
        # Renaming to a str of a relative path
        r = rel_join('fileAAA')
        q.rename(r)
        self.assertEqual(os.stat(r).st_size, size)
        self.assertFileNotFound(q.restat)

    @with_symlinks
    def test_symlink_to(self):
        P = self.cls(BASE)
        target = P['fileA']
        # Symlinking a path target
        link = P['dirA', 'linkAA']
        link.symlink_to(target)
        self.assertEqual(link.stat(), target.stat())
        self.assertNotEqual(link.lstat(), target.stat())
        # Symlinking a str target
        link = P['dirA', 'linkAAA']
        link.symlink_to(str(target))
        self.assertEqual(link.stat(), target.stat())
        self.assertNotEqual(link.lstat(), target.stat())

    def test_is_dir(self):
        P = self.cls(BASE)
        self.assertTrue(P['dirA'].is_dir())
        self.assertFalse(P['fileA'].is_dir())


class PathTest(_BasePathTest):
    cls = pathlib.Path

    def test_concrete_class(self):
        p = self.cls('a')
        self.assertIs(type(p),
            pathlib.NTPath if os.name == 'nt' else pathlib.PosixPath)

    def test_unsupported_flavour(self):
        if os.name == 'nt':
            self.assertRaises(NotImplementedError, pathlib.PosixPath)
        else:
            self.assertRaises(NotImplementedError, pathlib.NTPath)


@only_posix
class PosixPathTest(_BasePathTest):
    cls = pathlib.PosixPath

    def _check_symlink_loop(self, *args):
        path = self.cls(*args)
        with self.assertRaises(ValueError):
            print(path.resolve())

    @with_symlinks
    def test_resolve_loop(self):
        # Loop detection for broken symlinks under POSIX
        P = self.cls
        # Loops with relative symlinks
        os.symlink('linkX/inside', join('linkX'))
        self._check_symlink_loop(BASE, 'linkX')
        os.symlink('linkY', join('linkY'))
        self._check_symlink_loop(BASE, 'linkY')
        os.symlink('linkZ/../linkZ', join('linkZ'))
        self._check_symlink_loop(BASE, 'linkZ')
        # Loops with absolute symlinks
        os.symlink(join('linkU/inside'), join('linkU'))
        self._check_symlink_loop(BASE, 'linkU')
        os.symlink(join('linkV'), join('linkV'))
        self._check_symlink_loop(BASE, 'linkV')
        os.symlink(join('linkW/../linkW'), join('linkW'))
        self._check_symlink_loop(BASE, 'linkW')


if pathlib.supports_openat:
    class _RecordingOpenatAccessor(pathlib._OpenatAccessor):
        """A custom Accessor implementation to inspect the resolve() algorithm.
        """

        def __init__(self):
            super().__init__()
            self._readlinkat_fds = []
            self._walk_fds = []

        def readlinkat(self, dirfd, path, name):
            self._readlinkat_fds.append((dirfd, name))
            return super().readlinkat(dirfd, path, name)

        def walk_down(self, dirfd, path, name):
            self._walk_fds.append((dirfd, name))
            return super().walk_down(dirfd, path, name)


class Mock:
    def __init__(self, fullname):
        parts = fullname.split('.')
        obj = __import__('.'.join(parts[:-1]))
        for part in parts[1:]:
            module = obj
            obj = getattr(obj, part)
        self.module = module
        self.qualname = parts[-1]
        self.orig_func = obj

    def __enter__(self):
        def wrapper(*args, **kwargs):
            self.calls += 1
            return self.orig_func(*args, **kwargs)
        self.calls = 0
        setattr(self.module, self.qualname, wrapper)
        return self

    def __exit__(self, *_):
        setattr(self.module, self.qualname, self.orig_func)


@unittest.skipUnless(pathlib.supports_openat,
                     "test needs the openat() family of functions")
@only_posix
class PosixOpenatPathTest(PosixPathTest):
    cls = staticmethod(
        lambda *args, **kwargs:
        pathlib.PosixPath(*args, use_openat=True, **kwargs)
    )

    def _check_symlink_loop(self, *args):
        # with openat(), ELOOP is returned as soon as you try to construct
        # the path
        with self.assertRaises(OSError) as cm:
            path = self.cls(*args)
            path.resolve()
        self.assertEqual(cm.exception.errno, errno.ELOOP)

    def _check_resolve_relative(self, p, expected):
        self.assertIsInstance(p._accessor, pathlib._OpenatAccessor)
        p._accessor = _RecordingOpenatAccessor()
        q = p.resolve()
        self.assertEqual(q, expected)
        # Only the first lookup was absolute
        def _check_fds(fds):
            self.assertEqual(pathlib._NO_FD, fds[0][0])
            for fd, name in fds[1:]:
                self.assertGreaterEqual(fd, 0)
                self.assertFalse(name.startswith("/"), name)
        _check_fds(p._accessor._readlinkat_fds)
        _check_fds(p._accessor._walk_fds)

    def _check_resolve_absolute(self, p, expected):
        self.assertIsInstance(p._accessor, pathlib._OpenatAccessor)
        p._accessor = _RecordingOpenatAccessor()
        q = p.resolve()
        self.assertEqual(q, expected)
        # At least one other lookup was absolute
        def _check_fds(fds):
            self.assertEqual(pathlib._NO_FD, fds[0][0])
            self.assertTrue(any(fd == pathlib._NO_FD
                                for fd, _ in fds[1:]), fds)
        _check_fds(p._accessor._readlinkat_fds)
        _check_fds(p._accessor._walk_fds)

    def test_weakref_same_path(self):
        # Implementation detail: separate weakrefs must be created even
        # when two paths hash the same
        n = len(pathlib.Path._wrs)
        a = self.cls(BASE)
        b = self.cls(BASE)
        self.assertEqual(hash(a), hash(b))
        self.assertEqual(len(pathlib.Path._wrs), n + 2)
        del a, b
        support.gc_collect()
        self.assertEqual(len(pathlib.Path._wrs), n)

    def test_iter(self):
        with Mock("os.fdlistdir") as mock_fdlistdir, \
             Mock("os.listdir") as mock_listdir:
            super().test_iter()
        self.assertEqual(mock_fdlistdir.calls, 1)
        self.assertEqual(mock_listdir.calls, 0)

    def test_cwd(self):
        p = pathlib.PosixPath.cwd(use_openat=True)
        self._test_cwd(p)

    # XXX can't mock os.openat since _OpenatAccessor caches the os.openat lookup.


@only_nt
class NTPathTest(_BasePathTest):
    cls = pathlib.NTPath


def test_main():
    support.run_unittest(
        PosixFlavourTest, NTFlavourTest,
        PurePosixPathTest, PureNTPathTest, PurePathTest,
        PosixPathAsPureTest, NTPathAsPureTest,
        PosixPathTest, PosixOpenatPathTest, NTPathTest, PathTest,
    )

if __name__ == "__main__":
    test_main()
