#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
import optparse
import os
import PIL.Image
import shutil

try:
    import cStringIO
    StringIO = cStringIO
except ImportError:
    import StringIO

import sys
import time
import urllib
import xml.dom.minidom
import deepzoom

# http://code.activestate.com/recipes/412982-use-pil-to-make-a-contact-sheet-montage-of-images/


def open_half( filename ):
  return half( PIL.Image.open( filename ) )
def half( image ):
  return image.resize( (image.size[0]/2, image.size[1]/2) , PIL.Image.ANTIALIAS )

# 0 1
# 2 3
def combine4( filenames, dest ):
  # we know image0 always exists ( top-left corner )
  image0 = open_half( filenames[0] )
  size0 = image0.size
  width = size0[0]
  height = size0[1]
  insertions = []
  insertions.append( (image0, ( 0, 0, size0[0], size0[1] )) )
  try: # top-right
    image = open_half( filenames[1] )
    size = image.size
    insertions.append( (image, ( size0[0], 0, size0[0] + size[0], size[1] )) )
    width += size[0]
  except Exception:
    None
  try: # bottom-left
    image = open_half( filenames[2] )
    size = image.size
    insertions.append( (image, ( 0, size0[1], size0[0], size0[1] + size[1] )) )
    height += size[1]
  except Exception:
    None
  try: # bottom-right
    image = open_half( filenames[3] )
    size = image.size
    insertions.append( ( image,  ( size0[0], size0[1], size0[0] + size[0], size0[1] + size[1] )) )
  except Exception:
    None
  new_image = PIL.Image.new('RGB', (width, height), (255,255,255))
  for ins in insertions:
    new_image.paste( ins[0], ins[1] )
  new_image.save( dest )


class Pyramid(object):
  def __init__(self, base_path, width, height, tile_size, tile_overlap, tile_format):
    self.base_path = base_path
    self.width = width
    self.height = height
    self.tile_size = tile_size
    self.tile_overlap = tile_overlap
    self.tile_format = tile_format
    self.descriptor = deepzoom.DeepZoomImageDescriptor( width, height, tile_size, tile_overlap, tile_format )
  
  def generate_v0( self ):
    v0 = Version( self, 0 )
    v0.generate()

class Version(object):
  def __init__(self, pyramid, version_number):
    self.pyramid = pyramid
    self.version_number = version_number
    
    # pyramid_path/dest/dzi/v0/...
    self.base_path = "%s/dest/dzi/v%s" % (pyramid.base_path, version_number)
    # pyramid_path/v0 ( where the user-generate tiles reside )
    self.source_tiles_path = "%s/v%s" % ( pyramid.base_path, version_number )
    self.levels = {} # cache to hold all level objects
  
  def get_level( self, level_number ):
    """Returns Level object or None if level is beyond top level"""
    if level_number >= self.pyramid.descriptor.num_levels:
      return None
    if not level_number in self.levels:
      self.levels[level_number] = Level( self, level_number )
    return self.levels[level_number]
  
  def generate( self ):
    print "generating version %s" % self.version_number
    # create destination folder
    if not os.path.exists(self.base_path): os.makedirs(self.base_path)
    # save DZI xml file
    self.pyramid.descriptor.save( self.base_path + '/dzi.xml' )
    
    # calculate the maximum level according to dimensions
    max_level_number = self.pyramid.descriptor.num_levels - 1 # we subtract 1 because they start in 0
    
    # create all level objects
    # ( except the last two levels which are useless )
    level_nums = range( 3, self.pyramid.descriptor.num_levels )
    level_nums.reverse()

    for i in level_nums:
      self.get_level( i ).generate()

class Level(object):
  def __init__(self, version, level_number):
    self.version = version
    self.level_number = level_number
    
    self.pyramid = version.pyramid # handy reference to pyramid
    self.descriptor = version.pyramid.descriptor # handy reference to descriptor
    
    # v0/dzi_files/11/...
    self.base_path = "%s/dzi_files/%s" % ( self.version.base_path, self.level_number )
    # true if this is the max level in the pyramid ( level 11, for example )
    self.is_max_level = level_number is ( self.descriptor.num_levels - 1 )
    # Number of tiles in this level (columns, rows)
    self.num_tiles = self.descriptor.get_num_tiles( self.level_number )
    
    self.upper_level = version.get_level( level_number + 1 )
  
  # TODO: add a 'log' file that keeps track of progress
  # and allows us to resume
  # also, to skip the complete level when finished
  def generate( self ):
    print "generating level %s" % self.level_number
    # create level folder
    if not os.path.exists(self.base_path): os.makedirs(self.base_path)
    # TODO: log file
    
    # start looping and generating tiles
    for x in range( self.num_tiles[0] ):
      for y in range( self.num_tiles[1] ):
        tile = self.get_tile( x, y )
        tile.generate()

  def get_tile( self, x, y ):
    # Tile objects are not cached
    # ( GC considerations, as there will be millions of Tiles )
    return Tile( self, x, y )

class Tile(object):
  def __init__( self, level, x, y ):
    self.level = level
    self.version = level.version
    self.pyramid = level.version.pyramid
    self.descriptor = level.version.pyramid.descriptor
    self.x = x
    self.y = y
    self.filename = "%s_%s.%s" % ( x, y, self.pyramid.tile_format )
    self.dest_path = os.path.abspath( "%s/%s" % ( self.level.base_path, self.filename ) )
    self._parent_tiles = None

  def generate( self ):
    assert self.within_bounds, "Cannot generate an out of bounds Tile %s" % self.dest_path
    if not self.is_generated:
      # this is where most of the algorithms are implemented
      # this is a 2 by 3 decision matrix based on the following factors:
      # axis one
      is_level_m = self.level.level_number is ( self.descriptor.num_levels - 1 )
      ls_level_m1 = self.level.level_number is ( self.descriptor.num_levels - 2 )
      is_level_n = self.level.level_number < ( self.descriptor.num_levels - 2 )
      # axis two
      is_version_0 = self.version.version_number is 0
      is_version_n = self.version.version_number > 0
      
      if is_version_0 and is_level_m:
        # link to source tiles directly
        # print "LINK: %s --> %s" % ( self.source_tile_image_path, self.dest_path )
        os.symlink( self.source_tile_image_path, self.dest_path )
      
      elif is_version_0 and ( ls_level_m1 or is_level_n ):
        if self.any_parent_tile_has_changed:
          self.generate_from_parent_tiles()
  
  # parent tiles are the four tiles that, when combined and resized,
  #   create this tile
  # they are returned as a list of 4 Tile objects
  # be sure to check if these tiles are within bounds
  @property
  def parent_tiles( self ):
    assert not self.level.is_max_level, 'Cannot get the parent tiles of a tile from max level'
    if self._parent_tiles:
      return self._parent_tiles
    x = self.x * 2
    y = self.y * 2
    lev = self.level.upper_level
    self._parent_tiles = [ lev.get_tile(x, y), lev.get_tile(x+1, y), lev.get_tile(x, y+1), lev.get_tile(x+1, y+1)  ]
    return self._parent_tiles
  
  @property
  def any_parent_tile_has_changed( self ):
    for pt in self.parent_tiles:
      if pt.has_changed_since_last_version:
        return True
    return False
  
  @property
  def is_generated(self):
    """Checks to see if we have been generated or not"""
    return os.path.exists(self.dest_path)
  
  @property
  def within_bounds(self):
    nt = self.level.num_tiles
    return ( self.x < nt[0] ) and ( self.y < nt[1] )

  @property
  def source_tile_image_path(self):
    assert self.level.is_max_level, 'Only max level Tiles can have a source tile image'
    return os.path.abspath( "%s/%s" % ( self.version.source_tiles_path, self.filename ) )
  
  @property
  def has_source_tile_image(self):
    return os.path.exists(self.source_tile_image_path)

  @property
  def has_changed_since_last_version(self):
    assert self.is_generated, "Cannot check for changes on a Tile that has not been generated: %s" % self.dest_path 
    # if our version is v0, we are always changed
    if self.version.version_number is 0:
      return True
    # if our file exists and is not a symlink, then we have also changed
    if not os.path.islink( self.dest_path ):
      return True
    # a special case:
    # if we are on Level M, we may be a a symlink to a new file in the
    # version's sources folder, which is considered a change
    if self.level.is_max_level and self.has_source_tile_image:
      return True
    return False

  def generate_from_parent_tiles(self):
    files = [ (tile.dest_path if tile.within_bounds else None ) for tile in self.parent_tiles ]
    combine4( files, self.dest_path )


################################################################################
################################# MAIN #######################################
################################################################################

def main():
  # ./sandbox/girls_fastpyramid 1480, 940
  # ./sandbox/galaxy_fastpyramid 5920, 6000
  # ./sandbox/biggirls_fastpyramid 25000, 16667  
  path = './sandbox/biggirls_fastpyramid'
  # cleanup path if already exists
  dest_path = path + '/dest'
  if os.path.exists(dest_path): shutil.rmtree( dest_path )
  # generate version zero
  fp = Pyramid( path, 25000, 16667 , 254, 0, 'png' )
  fp.generate_v0()

main()
