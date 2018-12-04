#!/usr/bin/env python3
# Copyright © 2018 Marty White under the GNU GPLv3+
'''
A Minecraft-like 2-D game, presented with an overhead view.

TODO:
  * Clarify class Thing vs objects of class Thing
    - Using Flyweight or not? (or some but not others)
    - Customized Things?  Certainly some, if crafting is my point.
    - Possibility for procedurally generated things?
  * Add more ores, lots more types of everything
  * Hide rock area interior until exposed
  * Add critters/creatures
  * More procedural map generation
  * (Re)consider using numpy to enable larger/faster maps
  * enable FULLSCREEN toggle
  * Better organized scaling, icon sizes, and fonts
    - Better managed themeing?
  * Create a crafting system (and inventory screen/manager)
      Crafting Screen layout:
        Held Inventory slots
        Furniture Inventory slots (if applicable)
        Crafting Area:
          Catalysts Present (row of icons, such as workbench, furnace, flasks, etc.)
          Recipies combo/button
            Show prototypical & saved recipies (name/icon) for available Catalysts & Materials
            Include save button
          Input Binders slots (binding agents to use, such as vine, tape, glue, nails, solder)
            multiple copies per slot?
          Input Materials & Structure Slots Grid (4x4 or perhaps other sizes)
            1 copy per slot
          Output Result Slot (a recipie may yield alternate results)
            Don't consume inputs until output is moved to an available inventory/container slot
            Repeated crafting is easy, just keep pulling more outputs
      Some crafting scenarios:
        vine binder + stick & stone -> stone hammer
        smelter catalyst + malachite -> copper (bar)
        forge catalyst + water & oil binders + hilt & 2 blades (or steel?) in a line -> short sword

In Minecraft & Terraria:
  * Player moves with WASD keys, looks and clicks on things with mouse (current tool implied).
  * Inventory (hot) bar of 9 or 10 items, a subset of player's inventory.  One item is always selected.
  * Selected item determines semantics of mouse clicks: use tool or place object.

Items in cells in the world vs items in inventory (or storage containers).
  * How does their behavior differ?
  * A cell may be empty or filled
    - empty may still mean ground/dirt/grass/water.
    - filled may be like wall-to-wall stone, or like an item left there.
Behaviors:
  * Render (to world tile, to inventory tile)
    - harvested materials can look or be different from what they are harvested from (perhaps nearly always)
      * trees vs wood, lumps of ore vs embedded ore
  * Use (when wielded, when emplaced)
    - harvesting tools, melee or ranged weapons, other tools, consuming (food, potions), light sources, reading
    - crafting stations, furniture, containers, walls and other structures
  * Not used by wielding or emplacing:
    - Clothing, armor, "accessories"
    - Materials and ingredients
  * Place (when wielded)
  * Take (when emplaced)
Can the cell be traversed by player & other creatures?
Can the stuff in the cell be manipulated by creatures?
Can the cell prevent flow of water (or air)?
Thought experiment #1:
  An empty cell is just rock/sand/dirt/grass you can walk on
  A non-empty cell may hold:
    * a tree, or a piece (or two?) of harvested log, or some planks of wood, or a bunch of sticks
    * a full volume of rock/ore/sand/dirt, or lumps or piles of such
    * an item
    * a creature
    * the player
Dwarf Fortress cells can hold arbitrary amounts, but then it requires more user interface to see what is in there.
Cells holding abritrary amounts vs holding just one type of thing
  Cells holding multiple items need some way to display all of them
    inventory screen?
    list of items on main screen?
Custom items vs generic
  Generic items of the same type are all interchangeable, and only need representing with a single identifier.
  Custom items might include:
    * quality (of manufacture and/or wear)
    * materials (base and adornments)
    * complete unique design schematic

Mainly: HOW TO REPRESENT?
  Two layers:
    ground: what is there when nothing is there (and probably immutable): rock/sand/dirt/grass/water
    surface: one (type of) thing: tree, logs, ore body, ore stone, table, bottle, axe, etc.
  Object/Thing/Item
    Non-custom Things probably just need a table (name & methods)
    Custom Things need to be able to hold their custom values. (class with instances)

An Iconography
  Visual Display
    Compositing
      cell
      plinth
      primary
      inscribed
      decoration
    Shapes
      Regular (orientations): triangle (4), square (2), pentagon (2), hexagon (2), circle
      polyominoes
    Line
      opaque, translucent
      solid, dotted, dashed
    Color
      edge
      fill
      1,2,3,4 tone
    Texture - checks, dots, lines
    Text - One, Two, or Three letters (like chemistry), short labels, generated description
  Meanings
    natural color, shape
    animal, vegetable, mineral

'''

import sys, enum, math, random, glob, colorsys

#import numpy as np
import pygame

import windowing
from windowing import *

DEBUG = False
def IFDEBUG(value):
  if DEBUG: return value
  else: return None

SECOND = 1000  # conversion factor from seconds to standard units (miliseconds)

manager = None

def ceildiv(n, d):  # numerator or dividend, denominator or divisor
  'Integer division, but rounding up.'
  return (n + (d-1)) // d

def ChessboardDistance(p, q):
  # A.K.A. Chebyshev distance.
  "Return the distance between p and q if you can only move horizontally, vertically, or on a 45 degree diagonal."
  return max( abs(p[0]-q[0]), abs(p[1]-q[1]) )

class Thing:

  def __init__(self):
    pass

  def Name(self):
    return self.__class__.__name__

  def GetColor(self): return (127,127,127)

  icon_cache = {}

  @classmethod
  def FlushIconCache(cls):
    cls.icon_cache = {}

  def LoadIcon(self):
    # TODO:
    #  walk up the inheritance tree for names
    #  use fnmatch?
    name = self.Name().lower()
    for filename in glob.glob('icons/'+self.Name().lower()+'.png'):
      icon = pygame.image.load(filename)
      key = (name, icon.get_size())
      #print(key)
      Thing.icon_cache[key] = icon
      return icon
    return None

  def GetIcon(self, size=(64,64)):
    key = (self.Name().lower(), (size[0],size[1]))
    if size[0] < 1 or size[1] < 1:
      key = (None, (0,0))  # all zero-size surfaces are alike
    if not key in Thing.icon_cache:
      img = pygame.Surface( size, pygame.SRCALPHA )
      srcIcon = self.LoadIcon()
      DROPSHADOW = 2
      if srcIcon is None or size[0]<DROPSHADOW or size[1]<DROPSHADOW:
        img.fill( self.GetColor() )
        #pygame.draw.circle(img, (255,0,255), (16,16), 8)
      else:
        scaledSrcIcon = pygame.transform.scale(srcIcon, (size[0]-DROPSHADOW, size[1]-DROPSHADOW))
        img.blit(scaledSrcIcon, (DROPSHADOW,DROPSHADOW))
        scaledSrcIcon.fill( self.GetColor(), special_flags=pygame.BLEND_MAX )
        img.blit(scaledSrcIcon, (0,0))
      Thing.icon_cache[key] = img
    return Thing.icon_cache[key]

  def isTraversable(self): return False

  def UseDuration(self):
    'Time (in ms) it takes to use/swing this tool once'
    return SECOND*2
  def PowerEfficiency(self):
    'For a given power input (such as 100 W), what percent produces useful work with this tool?'
    return 10  # percentage
    # Active humans need about 2400 to 3000 food caloires (=8,368,000 to 12,552,000 joules) per day.
    # Humans (who consume 2000 food calories) expend around 100 W on average (record is around 430 W).
    # Human work efficiency is around 25%
  def EnergyToHarvest(self):
    'Energy required to chop/hew/harvest'
    # Given that 100 J/s is standard human power, but a wood axe in Terraria takes 5 seconds to cut down a tree.
    return 500  # joules

  def Use(self):
    pass

class FlyweightThing(Thing):

  instances = {}  # all instances of FlyweightThing and derived classes

  def __new__(cls):
    if not cls in FlyweightThing.instances:
      FlyweightThing.instances[cls] = super(FlyweightThing, cls).__new__(cls)
    return FlyweightThing.instances[cls]

class Terrain(FlyweightThing):
  'Terrain is what is left when a cell is bare empty'
class TerrainWater(Terrain):
  def GetColor(self): return (0,0,127)
class TerrainSaltWater(TerrainWater):
  pass
class TerrainLand(Terrain):
  def isTraversable(self): return True
  def GetColor(self): return (127,95,63)
class TerrainRock(TerrainLand):
  pass
class TerrainDirt(TerrainLand):
  pass
class TerrainSand(TerrainLand):
  def GetColor(self): return (230,201,114)
class TerrainGrass(TerrainLand):
  def GetColor(self): return (0,127,0)

# Most resources need a pre- and post- harvesting version.
#  Pre-harvested are marked "situ", for "in situ" or "in the situation".
# The Situ versions should have no icons or different icons.

class StoneSitu(FlyweightThing):
  def GetColor(self): return (127,127,127)
class Stone(StoneSitu):
  def GetColor(self): return (127,127,127)

class MalachiteSitu(FlyweightThing):
  #def GetColor(self): return (127,255,127)
  def GetColor(self): return (62,120,82)  # sampled from Wikipedia photo
class Malachite(MalachiteSitu):
  pass
class Copper(FlyweightThing):
  def GetColor(self): return (223,90,31)

class NativeSilverSitu(FlyweightThing):
  def GetColor(self): return (191,191,191)
class NativeSilver(NativeSilverSitu):
  pass
class Silver(FlyweightThing):
  def GetColor(self): return (217,217,217)

class NativeGoldSitu(FlyweightThing):
  def GetColor(self): return (223,218,70)
class NativeGold(NativeGoldSitu):
  pass
class Gold(FlyweightThing):
  def GetColor(self): return (255,247,25)

class WoodSitu(FlyweightThing):
  def GetColor(self): return (83,61,35)
class Wood(WoodSitu):
  def GetColor(self): return (171,126,72)
class Pickaxe(FlyweightThing):
  pass
class Woodaxe(FlyweightThing):
  def GetColor(self): return (153,113,64)
class Blade(FlyweightThing):
  def GetColor(self): return (127,127,127)
class Hammer(FlyweightThing):
  def GetColor(self): return (127,127,127)
class Vine(FlyweightThing):
  def GetColor(self): return (0, 127, 0)
class Table(FlyweightThing):
  def GetColor(self): return (204,150,86)

harvestRules = \
  [ (WoodSitu         , Woodaxe, Wood)
  , (StoneSitu        , Pickaxe, Stone)
  , (MalachiteSitu    , Pickaxe, Malachite)
  , (NativeSilverSitu , Pickaxe, NativeSilver)
  , (NativeGoldSitu   , Pickaxe, NativeGold)
  , (Copper           , Pickaxe, Copper)
  , (Silver           , Pickaxe, Silver)
  , (Gold             , Pickaxe, Gold  )
  , (Vine             , None,    Vine)
  ]

keyToWalkDirection = \
  { pygame.K_LEFT  : (-1, 0)
  , pygame.K_KP4   : (-1, 0)
  , pygame.K_a     : (-1, 0)
  , pygame.K_RIGHT : ( 1, 0)
  , pygame.K_KP6   : ( 1, 0)
  , pygame.K_d     : ( 1, 0)
  , pygame.K_UP    : ( 0,-1)
  , pygame.K_KP8   : ( 0,-1)
  , pygame.K_w     : ( 0,-1)
  , pygame.K_DOWN  : ( 0, 1)
  , pygame.K_KP2   : ( 0, 1)
  , pygame.K_s     : ( 0, 1)
  }

keyToActDirection = \
  { pygame.K_i : ( 0,-1)
  , pygame.K_j : (-1, 0)
  , pygame.K_k : ( 0, 1)
  , pygame.K_l : ( 1, 0)
  }

class Player(Observable):

  WIELD_TOOL = 1
  WIELD_MATERIAL = 2

  def __init__(self, world, initialpos=(10,10), **kwargs):
    super().__init__(**kwargs)
    self.world = world
    self.pos = [initialpos[0], initialpos[1]]
    self.inventory = [ [0,None] for i in range(40) ]
    self.inventory[0] = [1, Woodaxe()]
    self.inventory[1] = [1, Pickaxe()]
    self.inventory_selection = 0  # first item
    self.walkingTimeout = 0  # Time to wait until next walking can be performed
    self.walkingQueue = []   # Direction(s) to try to walk in - most recent first
    self.wieldType = None
    self.wieldPos = None
    self.throb = None   # None, or current position in throb cycle
    self.Changed()

  def PowerProduction(self): return 100  # in watts (a.k.a. joules/sec)

  def Changed(self, changed=True):
    self.changed = changed
    if changed:
      self.NotifyChange()

  def SelectInventory(self, idx):
    self.inventory_selection = idx
    self.Changed()

  def SelectInventoryAdjacent(self, offset):
    self.inventory_selection = (self.inventory_selection + offset) % 10
    self.Changed()

  def SelectedInventory(self):
    return self.inventory[self.inventory_selection]

  def GetInventory(self, i=None):
    if i is None:
      i = self.inventory_selection
    return self.inventory[i]

  def SwapInventory(self, i, j):
    if i < 0 or j < 0 or i >= len(self.inventory) or j >= len(self.inventory):
      return
    tmp = self.inventory[i]
    self.inventory[i] = self.inventory[j]
    self.inventory[j] = tmp
    self.Changed()

  def FindInventorySpace(self, some_thing, idx=None):
    'Return index where (more of?) thing can be added, or None'
    if idx is None:
      for i in range(len(self.inventory)):
        if self.inventory[i][1] == some_thing[1]:
          return i
      for i in range(len(self.inventory)):
        if self.inventory[i][0] == 0:
          return i
    else:
      if idx >= 0 and idx < len(self.inventory) and self.inventory[idx][1] == some_thing[1]:
        return idx
    print('No available inventory slot for', some_thing, 'at', idx)
    return None

  def AddInventory(self, some_thing, idx=None):
    'Add (count, thing) to inventory.  Add to slot idx if possible.'
    idx = self.FindInventorySpace(some_thing, idx)
    if not idx is None:
      self.inventory[idx] = [self.inventory[idx][0]+some_thing[0], some_thing[1]]
      print("Got {} {}".format(some_thing[0], some_thing[1].Name()))
      self.Changed()
      return idx
    return None

  def RemoveInventory(self, some_thing, idx=None):
    if idx is None:
      indexes = range(len(self.inventory))
    elif idx >= 0 and idx < len(self.inventory):
      indexes = [idx]
    else:
      indexes = []
    removed = 0
    for i in indexes:
      if self.inventory[i][1] == some_thing[1]:
        count = min(some_thing[0], self.inventory[i][0])
        self.inventory[i][0] -= count
        some_thing = [some_thing[0] - count, some_thing[1]]
        removed += count
        if self.inventory[i][0] == 0:
          self.inventory[i][1] = None
        print("Dropped {} {}".format(count, some_thing[1].Name()))
        if some_thing[0] == 0:
          break
    if removed:
      self.Changed()
      return (removed, some_thing[1])
    return (0, None)

  def HasThing(self, some_thing):
    count = 0
    for numthing, thing in self.inventory:
      if thing == some_thing[1]:
        count += numthing
    return count >= some_thing[0]
  
  def HasThings(self, thingList):
    return all(self.HasThing(t) for t in thingList)

  def GetInventoryImage(self, i, size, count=None):
    numthing, thing = self.inventory[i]
    if numthing and not thing is None and size>=0:
      MARGIN = 2
      img = pygame.Surface( (size,size), pygame.SRCALPHA)
      nameLabel = manager.GetFont('LABEL').render(thing.Name(), True, (0,0,0))
      img.blit(nameLabel, (MARGIN,size-MARGIN-nameLabel.get_height()))
      z = size - nameLabel.get_height() - MARGIN*2
      thingImg = thing.GetIcon( (z,z) )
      img.blit(thingImg, (MARGIN+size//2-z//2,MARGIN))
      if count is None:
        count = numthing
      if count != 1:
        countLabel = manager.GetFont('LABEL').render( str(count), True, (0,0,0) )
        img.blit(countLabel, (MARGIN,MARGIN))
      return img
    return None

  def CanOccupy(self, newpos):
    'Return True if player can be at the given position.'
    if newpos[0] < 0 or newpos[1] < 0 or newpos[0] >= self.world.sz[0] or newpos[1] >= self.world.sz[1]:
      return False
    terrain = self.world.ground[newpos[1]][newpos[0]]
    numthing, thing = self.world.things[newpos[1]][newpos[0]]
    if terrain.isTraversable() and (numthing==0 or thing is None or thing.isTraversable()):
      return True
    return False

  def MoveTo(self, newpos):
    'Unconditionally move player to newpos - assumes CanOccupy() was already consulted.'
    if not self.wieldPos is None:
      self.wieldPos = ( self.wieldPos[0] + newpos[0] - self.pos[0]
                      , self.wieldPos[1] + newpos[1] - self.pos[1] )
    self.pos[0] = newpos[0]
    self.pos[1] = newpos[1]
    #print('player pos = {}'.format(self.pos))
    self.Changed()

  def CanUseAt(self, tool, hitpos):
    pass

  def WouldHarvestAt(self, hitpos):
    numtool, tool = self.SelectedInventory()
    if ChessboardDistance(hitpos, self.pos) <= 1:
      numtarget, target = self.world.things[hitpos[1]][hitpos[0]]
      if numtarget:
        for (xinput, xtool, xoutput) in harvestRules:
          if isinstance(target, xinput):
            if xtool is None or (isinstance(tool, xtool) and numtool):
              return (1,xoutput())
    return (0,None)

  def UsePrimaryAt(self, hitpos):
    numthing, thing = self.WouldHarvestAt(hitpos)
    if numthing and not thing is None:
      self.world.things[hitpos[1]][hitpos[0]] = (0,None)
      self.world.progress.pop(hitpos, None)
      self.Changed()
      self.world.Changed()
      self.AddInventory( (numthing, thing) )
      return True
    return False

  def UseSecondaryAt(self, xy):
    pass

  def OnWalkBegin(self, direction):
    if direction in self.walkingQueue:
      self.walkingQueue.remove(direction)
    self.walkingQueue.insert(0, direction)

  def OnWalkEnd(self, direction):
    if direction in self.walkingQueue:
      self.walkingQueue.remove(direction)

  def OnUsePrimaryBegin(self, hitpos):
    if self.wieldType is None:
      self.wieldType = Player.WIELD_TOOL
    self.wieldPos = hitpos

  def OnUseSecondaryBegin(self, hitpos):
    if self.wieldType is None:
      self.wieldType = Player.WIELD_MATERIAL
    self.wieldPos = hitpos

  def OnUsePrimaryUpdate(self, hitpos):
    self.wieldPos = hitpos
  OnUseSecondaryUpdate = OnUsePrimaryUpdate

  def OnUsePrimaryEnd(self):
    if self.wieldType is Player.WIELD_TOOL:
      self.wieldType = None
      self.wieldPos = None

  def OnUseSecondaryEnd(self):
    if self.wieldType is Player.WIELD_MATERIAL:
      self.wieldType = None
      self.wieldPos = None

  def UpdateWalking(self, dt):
    '''Movement model:
      * Movement is discrete and instantaneous.
      * But can only happen if player hasn't moved too recently.
      * Should happen whenever movement keys are down and player can move in one of those directions.
      * walkingTimeout tracks time to wait until player can move again.
      * walkingQueue list directions to walk in, in most-recent first priority.
    '''
    self.walkingTimeout -= dt
    if self.walkingTimeout < 0:
      self.walkingTimeout = 0
    if self.walkingTimeout <= 0:
      moved = False
      for direction in self.walkingQueue:
        newpos = [self.pos[0]+direction[0], self.pos[1]+direction[1]]
        if self.CanOccupy(newpos):
          self.MoveTo(newpos)
          self.walkingTimeout += SECOND//30
          moved = True
          break
      #if not moved and len(self.walkingQueue) == 1:
      #  print("Cannot walk that way.")

  def UpdateWielding(self, dt):
    '''Action model:
      * Swinging/using a tool/weapon should take a certain amount of time.
      * A resource being hewed/harvested should require a certain amount of "work" to harvest it.
      * A given tool should have a certain amount of efficiency in doing work.
      * Should happen whenever action key is down
      * world.progress tracks progress in harvesting a Thing
    '''
    if not self.wieldPos is None:
      numheld, held = self.SelectedInventory()
      if numheld and not held is None:
        if self.wieldType is Player.WIELD_TOOL:
          numthing, thing = self.WouldHarvestAt(self.wieldPos)
          if numthing and not thing is None:
            progress = self.world.progress.get(self.wieldPos, 0)
            if progress >= thing.EnergyToHarvest():
              self.UsePrimaryAt(self.wieldPos)
            else:
              j = dt * held.PowerEfficiency() // 10
              self.world.progress[self.wieldPos] = progress + j
              self.world.Changed()
        elif self.wieldType is Player.WIELD_MATERIAL:
          numtarget, target = self.world.things[self.wieldPos[1]][self.wieldPos[0]]
          if numtarget == 0 and numheld and ChessboardDistance(self.wieldPos, self.pos) == 1:
            if isinstance(held, (Wood, Stone, Malachite, NativeSilver, NativeGold, Copper, Silver, Gold)):
              (numremoved, removed) = self.RemoveInventory( (1,held), self.inventory_selection )
              if numremoved:
                self.world.things[self.wieldPos[1]][self.wieldPos[0]] = (numremoved, removed)
                self.world.Changed()

  def Update(self, dt):
    self.UpdateWalking(dt)
    self.UpdateWielding(dt)

class World(Observable):
  # Containing the terrain, player, inventory, etc.

  def __init__(self, *posargs, **kwargs):
    super().__init__(*posargs, **kwargs)
    self.sz = (1000,1000)
    self.ground = [ [ TerrainGrass() for r in range(self.sz[1]) ] for c in range(self.sz[0]) ]
    #self.ground = np.random.randint(0,4,self.sz)
    self.things = [ [ (0,None) for r in range(self.sz[1]) ] for c in range(self.sz[0]) ]
    self.GenerateTerrain()
    self.GenerateTrees()
    self.GenerateRock()
    self.progress = {}  # map from (x,y) to milliseconds remaining to finish choping/pickaxing/harvesting Thing
    self.player = Player(self)
    self.icons = {}
    print('{:,} cells'.format(self.sz[0]*self.sz[1]))
    self.player.Subscribe(CHANGE, self.OnChange)
    self.Changed()

  def GenerateTerrain(self):
    # Assuming ground[] is already just Grass
    for value in (TerrainSand(), TerrainWater()):
      for i in range(100):
        width = random.randrange(12,64)
        height = random.randrange(12,64)
        top = random.randrange(self.sz[1] - height)
        left = random.randrange(self.sz[0] - width)
        self.GroundFill(pygame.Rect(left, top, width, height), value)

  def GenerateTrees(self):
    for i in range(5000):
      self.things[random.randrange(self.sz[1])][random.randrange(self.sz[0])] = (1,Vine())
    for i in range(5000):
      self.things[random.randrange(self.sz[1])][random.randrange(self.sz[0])] = (1,WoodSitu())

  def GenerateRock(self):
    for i in range(100):
      width = random.randrange(12,128)
      height = random.randrange(12,128)
      top = random.randrange(self.sz[1] - height)
      left = random.randrange(self.sz[0] - width)
      r = pygame.Rect(left, top, width, height)
      self.ThingFill(r, (1, StoneSitu()))
      for j in range(random.randrange(2,16)):
        self.GenerateVein(r, (1,MalachiteSitu()) )
      for j in range(random.randrange(2,12)):
        self.GenerateVein(r, (1,NativeSilverSitu()) )
      for j in range(random.randrange(2,8)):
        self.GenerateVein(r, (1,NativeGoldSitu()) )

  def GenerateVein(self, rect, value):
    points = [(random.randrange(rect.left, rect.right), random.randrange(rect.top, rect.bottom))]
    p = points[0]
    for i in range(random.randrange(29)):
      p2 = (p[0]+random.randrange(-1,2), p[1]+random.randrange(-1,2))
      if self.CollidePoint(p2) and self.things[p2[1]][p2[0]][1] == StoneSitu() and not p2 in points:
        points.append(p2)
        p = p2
    for p in points:
      self.things[p[1]][p[0]] = value

  def Changed(self, changed=True):
    self.changed = changed
    if self.changed:
      self.NotifyChange()

  def OnChange(self, evt):
    self.Changed()

  def GroundFill(self, r, value):
    for row in range(r.height):
      for col in range(r.width):
        self.ground[r.top+row][r.left+col] = value
    self.Changed()

  def ThingFill(self, r, value):
    for row in range(r.height):
      for col in range(r.width):
        self.things[r.top+row][r.left+col] = value
    self.Changed()

  def Update(self, dt):
    self.player.Update(dt)

  def CollidePoint(self, p):
    'Is cell at coordinate p in the world?  (Or does it fall off the edge?)'
    return not( p[0] < 0 or p[1] < 0 or p[0] >= self.sz[0] or p[1] >= self.sz[1] )

def sinInterp(value, inLo, inHi, outLo, outHi):
  # TODO: replace with a table of additive color values
  return math.sin( value * (2*math.pi / (inHi-inLo)) ) * (outHi-outLo) + outLo

class WorldWnd(Window):

  # Render the world to the screen,
  # map input back to the world.

  def __init__(self, parent, rect, world, **kwargs):
    super().__init__(parent, rect, **kwargs)
    self.world = world
    self.player = world.player
    self.ZoomAbs(3)
    self.player.Subscribe(CHANGE, self.OnChange)
    self.world.Subscribe(CHANGE, self.OnChange)

  def ZoomAbs(self, power):
    self.zoomPower = power
    self.tilesize = 4 * 2**power
    self.Dirty()

  def ZoomRel(self, delta):
    z = self.zoomPower + int(delta)
    if z >= 0 and z < 6:
      self.ZoomAbs(z)

  def OnRender(self, surf):
    #print("WorldWnd.Render()")
    # How many world rows & cols fit on the screen?  (Round up to display partial rows & cols at edge)
    half_scr_rows = ceildiv(self.rect.height, self.tilesize*2)
    half_scr_cols = ceildiv(self.rect.width,  self.tilesize*2)
    # What range of world rows & cols to render?  Remember them for hit-testing.
    self.world_row_start = self.world.player.pos[1] - half_scr_rows
    self.world_row_stop  = self.world.player.pos[1] + half_scr_rows
    self.world_col_start = self.world.player.pos[0] - half_scr_cols
    self.world_col_stop  = self.world.player.pos[0] + half_scr_cols
    #print('half_scr_rows={}, half_scr_cols={}, toprow={}, leftcol={}'
    #      .format(half_scr_rows, half_scr_cols, self.world_row_start, self.world_col_start))
    for row in range(self.world_row_start, self.world_row_stop):
      #print('r{0}'.format(row), end='')
      for col in range(self.world_col_start, self.world_col_stop):
        left = self.rect.left + (col - self.world_col_start) * self.tilesize
        top  = self.rect.top  + (row - self.world_row_start) * self.tilesize
        r = pygame.rect.Rect(left, top, self.tilesize, self.tilesize)
        # TODO: reconfigure rendering to not have to call CollidePoint on every point
        if not self.world.CollidePoint( (col,row) ):
          #pygame.draw.rect(surf, (0,127-row%8*8,255-col%8*8), r)
          #pygame.draw.rect(surf, (0, 255-(int(math.sin(math.radians(45*(row%8)))*8)+8), 255-col%8*8), r)
          pygame.draw.rect(surf, (0, sinInterp(row%8,0,8,255-8,255), sinInterp(col%8,0,8,255-8,255)), r)
        else:
          terrain = self.world.ground[row][col]
          pygame.draw.rect(surf, terrain.GetColor(), r)
          numthing, thing = self.world.things[row][col]
          if numthing and not thing is None:
            icon = thing.GetIcon( (self.tilesize,self.tilesize) )
            surf.blit(icon, r)
            #pygame.draw.circle(surf, thing.GetColor(), r.center, 12)
            if (col,row) in self.world.progress:
              progressbar = pygame.rect.Rect(r.left+2, r.top+2, r.width-4, r.height/8)
              pygame.draw.rect(surf, (0,0,0), progressbar)
              progressbar.width = (progressbar.width-2) * self.world.progress[(col,row)] // thing.EnergyToHarvest()
              progressbar.height -= 2
              pygame.draw.rect(surf, (0,255,0), progressbar)
          if row==self.world.player.pos[1] and col==self.world.player.pos[0]:
            c = (255,255,0)
            radius = self.tilesize * 2 // 6
            if not self.world.player.throb is None:
              radius += int( (self.tilesize // 6) * math.sin(math.radians(self.world.player.throb)) )
            pygame.draw.circle(surf, c, r.center, radius)
            pygame.draw.circle(surf, (0,0,0), r.center, radius, 1)

  def MouseToWorldPos(self, pos):
    world_col = pos[0] // self.tilesize + self.world_col_start
    world_row = pos[1] // self.tilesize + self.world_row_start
    return (world_col, world_row)

  def OnMouseButtonDown(self, evt):
    #print("WorldWnd.OnMouseButtonDown")
    worldPos = self.MouseToWorldPos(evt.pos)
    #print("button {}: x,y = {},{} -> col={}, row={}".format(evt.button, evt.pos[0], evt.pos[1], world_col, world_row))
    if not self.world.CollidePoint(worldPos):
      return False
    if evt.button == 1:  # left mouse button
      self.player.OnUsePrimaryBegin(worldPos)
      return True
    elif evt.button == 3:  # right mouse button
      self.player.OnUseSecondaryBegin(worldPos)
      return True
    elif evt.button == 4:
      self.player.SelectInventoryAdjacent(-1)
    elif evt.button == 5:
      self.player.SelectInventoryAdjacent(1)
    return False

  def OnMouseMove(self, evt):
    if evt.buttons[0]:
      worldPos = self.MouseToWorldPos(evt.pos)
      if self.world.CollidePoint(worldPos):
        self.player.OnUsePrimaryUpdate(worldPos)
      return True
    return False

  def OnMouseButtonUp(self, evt):
    if evt.button == 1:
      self.player.OnUsePrimaryEnd()
      return True
    elif evt.button == 3:
      self.player.OnUseSecondaryEnd()
      return True
    return False

  def OnKeyDown(self, evt):
    if evt.key in keyToWalkDirection:
      self.player.OnWalkBegin( keyToWalkDirection[evt.key] )
      return True
    elif evt.key in keyToActDirection:
      direction = keyToActDirection[evt.key]
      hitpos = (self.player.pos[0]+direction[0], self.player.pos[1]+direction[1])
      self.player.OnUsePrimaryBegin(hitpos)
      return True
    elif evt.unicode == '?':
      print('player_pos = {}'.format(self.world.player.pos))
    return False

  def OnKeyUp(self, evt):
    if evt.key in keyToWalkDirection:
      self.player.OnWalkEnd( keyToWalkDirection[evt.key] )
      return True
    elif evt.key in keyToActDirection:
      self.player.OnUsePrimaryEnd()
      return True
    return False

def HSV2RGB(h,s,v):
  rgb = colorsys.hsv_to_rgb(h/360,s/100,v/100)
  return (int(rgb[0]*255),int(rgb[1]*255),int(rgb[2]*255))

class HotbarSlot(Button):

  def OnChange(self, evt):
    self.image = self.player.GetInventoryImage(self.idx, size=self.rect.width)
    self.Selected(self.idx == self.player.inventory_selection)
    self.Dirty()

class HotbarWnd(Window):

  HOTBAR_ENTRIES = 10
  MARGIN = 2
  BUTTON_MAX_SIZE = 64
  BODY_COLOR = HSV2RGB(30,10,80)
  FRAME_COLOR = HSV2RGB(30,20,70)
  SELECTION_COLOR = HSV2RGB(60,40,90)

  def __init__(self, parent, rect, world, **kwargs):
    super().__init__(parent, rect, **kwargs)
    self.world = world
    self.player = world.player
    self.buttons = []
    for i in range(self.HOTBAR_ENTRIES):
      b = HotbarSlot(self, text=IFDEBUG('slot {}'.format(i)))
      b.idx = i
      b.player = self.player
      self.buttons.append(b)
      self.player.Subscribe(CHANGE, b.OnChange)
      b.Subscribe(CLICK, self.OnClick)
    self.zoomPower = None
    self.ZoomAbs(3)
    self.player.Subscribe(CHANGE, self.OnChange)

  def OnClick(self, evt):
    print('HotbarWnd.OnClick({}), id={}'.format(evt, evt.sender.idx))
    self.player.SelectInventory(evt.sender.idx)

  def ZoomAbs(self, power):
    if power != self.zoomPower:
      self.zoomPower = power
      self.buttonSize = 8 * 2**power
      #self.hotbar_font = pygame.font.SysFont("sans serif", 2 * 2**power)
      #self.hotbar_font = pygame.font.SysFont("freemono", 2**power, bold=True)
      Thing.FlushIconCache()

  def ZoomRel(self, delta):
    z = self.zoomPower + int(delta)
    if z >= 0 and z < 6:
      self.ZoomAbs(z)

  def OnResize(self, oldSize):
    #print("HotbarWnd.OnResize()")
    for row in range(self.HOTBAR_ENTRIES):
      top = row * (self.buttonSize+self.MARGIN)
      r = pygame.rect.Rect(self.rect.left, top, self.buttonSize, self.buttonSize)
      self.buttons[row].Resize(r)
      self.buttons[row].image = self.world.player.GetInventoryImage(row, size=self.buttonSize)
      self.buttons[row].Selected(row == self.player.inventory_selection)

  def AutoResize(self):
    #height = min(self.parentWnd.rect.height, self.BUTTON_MAX_SIZE*self.HOTBAR_ENTRIES)
    height = self.parentWnd.rect.height
    #self.buttonSize = min(self.BUTTON_MAX_SIZE, height // self.HOTBAR_ENTRIES)
    self.buttonSize = height // self.HOTBAR_ENTRIES - self.MARGIN
    r = pygame.Rect(0,0, self.buttonSize, (self.buttonSize+self.MARGIN)*self.HOTBAR_ENTRIES)
    r.top = self.parentWnd.rect.height // 2 - height // 2
    self.Resize(r)

  def OnRender(self, surf):
    surf.fill( pygame.Color('0xC0C0C0') )

  def OnMouseButtonDown_(self, evt):
    #print("HotbarWnd.OnMouseButtonDown(button={})".format(evt.button))
    if evt.button == 1:
      i = evt.pos[1] // self.buttonSize
      if i < self.HOTBAR_ENTRIES:
        self.player.SelectInventory(i)
        return True
    elif evt.button == 4:
      self.player.SelectInventoryAdjacent(-1)
    elif evt.button == 5:
      self.player.SelectInventoryAdjacent(1)
    return False

  def OnKeyDown(self, evt):
    #print("HotbarWnd.OnKeyDown()")
    if evt.key >= pygame.K_0 and evt.key <= pygame.K_9:
      i = '1234567890'.find(evt.unicode)
      if i >= 0 and i <= 9:
        self.player.SelectInventory(i)
        return True
    return False

class InventorySlot(DraggableHolder):

  def OnMouseButtonDown(self, evt):
    if self.player.GetInventory(self.idx)[1]:
      super().OnMouseButtonDown(evt)

  def OnDrop(self, evt):
    if isinstance(evt.data, dict):
      if 'inventory' in evt.data:
        i = evt.data['inventory']
        print("dropped slot {} '{}' on slot {} '{}'".format(i, evt.sender.text, self.idx, self.text))
        self.player.SwapInventory(i, self.idx)
        self.Dirty()
        evt.sender.Dirty()
      elif 'product' in evt.data:
        print('got product drop')
        if self.player.HasThings( (1, t) for t in evt.data['consumables'] ):
          for t in evt.data['consumables']:
            numremoved, thingremoved = self.player.RemoveInventory( (1, t) )
          self.player.AddInventory( (1, evt.data['product']) )
    else:
      print('ignoring drop')

  def OnRender(self, surf):
    #print('InventorySlot({}).OnRender()'.format(self.text))
    self.image = self.player.GetInventoryImage(self.idx, size=self.rect.width)
    return super().OnRender(surf)

class InventoryPanel(Window):

  def __init__(self, parent, player, **kwargs):
    super().__init__(parent, **kwargs)
    self.player = player
    self.islots = []
    for i in range(len(self.player.inventory)):
      slot = InventorySlot(self, data={'inventory':i, 'player':player}, text=IFDEBUG('#{:02d}'.format(i)) )
      slot.idx = i
      slot.player = self.player
      self.islots.append(slot)
    #self.player.Subscribe(CHANGE, self.OnChange)

  def OnResize(self, oldSize):
    ilen = len(self.player.inventory)
    cols = ceildiv(ilen,10)
    rows = 10
    z = 64
    margin = 0
    if rows*(z+margin) > self.rect.height:
      z = (self.rect.height // rows) - margin
    i = 0
    for col in range(ceildiv(ilen,rows)):
      left = col * (z+margin)
      for row in range(rows):
        top = row * (z+margin)
        self.islots[i].Resize(pygame.Rect(left,top,z,z))
        #self.islots[i].image = self.player.GetInventoryImage(i, size=z)
        i += 1

class MatrixSlot(DraggableHolder):

  #def __init__(self, parentWnd, **kwargs):
  #  super().__init__(parentWnd, **kwargs)
  #  self.thing = None

  def OnMouseButtonDown(self, evt):
    if self.data['thing']:
      super().OnMouseButtonDown(evt)

  def BeginDragging(self, evt):
    super().BeginDragging(evt)
    self.data = self.data.copy()
    self.data['thing'] = None
    self.UpdateImage()
    self.NotifyChange()

  def OnDrop(self, evt):
    if isinstance(evt.data, dict):
      if 'inventory' in evt.data:
        print('got inventory drop')
        player = evt.data['player']
        i = evt.data['inventory']
        self.data['thing'] = player.GetInventory(i)[1]
        self.UpdateImage()
        self.NotifyChange()
        return
      elif 'matrix' in evt.data:
        print('got matrix drop')
        self.data['thing'] = evt.data['thing']
        self.UpdateImage()
        self.NotifyChange()
        return
    print('ignoring drop')

  def UpdateImage(self):
    if self.data['thing'] is None:
      self.image = None
    else:
      self.image = self.data['thing'].GetIcon((self.rect.width, self.rect.height))
    self.Dirty()

class MatrixPanel(Window):

  def __init__(self, parent, **kwargs):
    super().__init__(parent, **kwargs)
    self.size = 64
    self.rank = 4
    self.matrix = [[None]*self.rank for _ in range(self.rank)]
    for row in range(self.rank):
      for col in range(self.rank):
        idx = (row,col)
        slot = MatrixSlot(self, data={'matrix':idx,'thing':None}, text=IFDEBUG('{},{}'.format(row,col)))
        slot.idx = idx
        self.matrix[row][col] = slot
        slot.Subscribe(CHANGE, self.OnChange)  # super.OnChange cascades to this window's subscribers by default
    self.OnResize(None)

  def OnResize(self, oldSize):
    z = self.rank * self.size
    left = (self.rect.width  - z) // 2
    top  = (self.rect.height - z) // 2
    for row in range(self.rank):
      for col in range(self.rank):
        r = pygame.Rect(left+col*self.size, top+row*self.size, self.size, self.size)
        self.matrix[row][col].Resize(r)

  def GetThingMatrix(self):
    things = [[None]*self.rank for _ in range(self.rank)]
    for row in range(self.rank):
      for col in range(self.rank):
        things[row][col] = self.matrix[row][col].data['thing']
    return things

class ProductSlot(DraggableHolder):

  def SetProduct(self, consumables, thing):
    if consumables is None or thing is None:
      self.data = None
      self.image = None
    else:
      self.data = { 'consumables': consumables, 'product' : thing }
      self.image = thing.GetIcon((self.rect.width, self.rect.height))
    self.Dirty()

crafting_productions = \
  [ ([[Stone],[Wood]], Hammer)
  , ([[Blade],[Wood]], Woodaxe)
  , ([[Malachite]], Copper)
  , ([[NativeSilver]], Silver)
  , ([[NativeGold]], Gold)
  , ([[Stone]], Blade)
  ]

def TrimMatrix(matrix):
  while matrix and all(cell is None for cell in matrix[0]):
    matrix = matrix[1:]
  while matrix and all(cell is None for cell in matrix[-1]):
    matrix = matrix[:-1]
  while matrix and matrix[0] and all(row[0] is None for row in matrix):
    matrix = [row[1:] for row in matrix]
  while matrix and matrix[0] and all(row[-1] is None for row in matrix):
    matrix = [row[:-1] for row in matrix]
  return matrix

class CraftingWnd(Window):

  def __init__(self, parent, world, **kwargs):
    super().__init__(parent, isModal=True, **kwargs)
    self.world = world
    self.inventWnd = InventoryPanel(self, world.player, text='inventory panel')
    self.matrixWnd = MatrixPanel(self, text='matrix panel')
    self.outputSlot = ProductSlot(self, text='output')
    self.matrixWnd.Subscribe(CHANGE, self.OnMatrixChanged)
    self.world.player.Subscribe(CHANGE, self.OnPlayerChanged)
    self.matrix = [[]]
    self.consumables = []

  def OnResize(self, oldSize):
    r = self.localRect.inflate(-8,-8)
    self.inventWnd.Resize(pygame.Rect(r.left, r.top, r.width//3, r.height))
    self.matrixWnd.Resize(pygame.Rect(self.inventWnd.rect.right, r.top, r.width//3, r.height//2))
    self.outputSlot.Resize(pygame.Rect(self.matrixWnd.rect.centerx-32, self.matrixWnd.rect.bottom, 64,64))

  def OnKeyDown(self, evt):
    if evt.key == pygame.K_ESCAPE:
      self.SetVisible(False)
      return True
    return False

  def OnMatrixChanged(self, evt):
    # a MatrixSlot changed its contents
    self.matrix = self.matrixWnd.GetThingMatrix()
    #print('matrix =', self.matrix)
    self.matrix = TrimMatrix(self.matrix)
    #print('trimmed matrix =', self.matrix)
    self.UpdateMatrixProduct()

  def OnChange(self, evt):
    print("CraftingWnd.OnChange() !")

  def OnPlayerChanged(self, evt):
    # Note that this is called every time the player changes in any way,
    # even when this window is not visible or enabled!
    self.UpdateConsumables()
    self.UpdateOutputEnabled()

  def UpdateConsumables(self):
    self.consumables = [ thingy for rowlist in self.matrix for thingy in rowlist if not thingy is None ]
    #print('consumables are', self.consumables)

  def UpdateMatrixProduct(self):
    self.UpdateConsumables()
    for (pattern, result) in crafting_productions:
      #print('comparing',pattern)
      found = True
      if len(pattern) != len(self.matrix) or len(pattern[0]) != len(self.matrix[0]):
        found = False
      else:
        for (row, col) in ((r,c) for r in range(len(pattern)) for c in range(len(pattern[r]))):
          if not isinstance(self.matrix[row][col], pattern[row][col]):
            found = False
            break
      if found:
        break
    if found:
      #print('Pattern match: {} -> {}'.format(pattern,result))
      self.outputSlot.SetProduct(self.consumables, result())
      self.UpdateOutputEnabled()
    else:
      self.outputSlot.SetProduct(None, None)

  def UpdateOutputEnabled(self):
    self.outputSlot.SetEnabled( self.world.player.HasThings( (1, t) for t in self.consumables ) )

class AppWnd(Window):

  def __init__(self, parent, screen, world, **kwargs):
    super().__init__(parent, screen.get_rect(), **kwargs)
    self.world = world
    self.worldWnd = WorldWnd(self, screen.get_rect(), world, text='worldWnd')
    #self.dummyWnd = Button(self, pygame.Rect(128,64,256,128) )
    #self.dummyWnd.Subscribe(windowing.CLICK, self.DummyClick)
    self.hotbarWnd = HotbarWnd(self, None, world, text='hotbarWnd')
    self.craftWnd = CraftingWnd(self, world, text='crafting window')
    self.craftWnd.SetVisible(False)
    self.ResizeChildren()

  def DummyClick(self, evt):
    print('DummyClick!')

  def ResizeChildren(self):
    self.worldWnd.Resize(pygame.Rect((0,0),self.rect.size))
    self.hotbarWnd.AutoResize()
    self.craftWnd.Resize(self.rect.inflate(-32,-32))

  def OnResize(self, oldRect):
    self.ResizeChildren()

  def OnKeyDown(self, evt):
    if evt.unicode == '+':
      self.ZoomRel(1)
      return True
    elif evt.unicode == '-':
      self.ZoomRel(-1)
      return True
    elif evt.key in (pygame.K_ESCAPE,):
      self.StartCraftingMode()
      return True
    return False

  def ZoomRel(self, delta):
    self.worldWnd.ZoomRel(delta)
    self.hotbarWnd.ZoomRel(delta)
    self.ResizeChildren()

  def StartCraftingMode(self):
    self.craftWnd.SetVisible(True)
    #self.craftWnd.Resize(pygame.Rect(self.rect))

def DebugKeystrokeEvent(evt):
  keynames = []
  modnames = []
  for a in dir(pygame):
    if a.startswith('K_'):
      value = getattr(pygame, a)
      if value == evt.key:
        keynames.append(a)
    elif a.startswith('KMOD_'):
      value = getattr(pygame, a)
      if evt.mod & value:
        modnames.append(a)
  fields = [ 'key = {}'.format(evt.key) ]
  if keynames: fields.append( '{}'.format(keynames) )
  fields.append( 'mod = {:04X}'.format(evt.mod) )
  if modnames: fields.append( '{}'.format(modnames) )
  if evt.type is pygame.KEYDOWN and len(evt.unicode):
    fields.append('unicode = {:04X}'.format(ord(evt.unicode)) )
    if evt.unicode.isprintable():
      fields.append( '"{}"'.format(evt.unicode) )
  print(' '.join(fields))

def ChooseVideoMode(margin=(96,96)):
  modes = pygame.display.list_modes()
  if modes is -1:
    return (0,0)
  vi = pygame.display.Info()
  if vi.current_h > margin[1] and vi.current_w > margin[0]:
    target = (vi.current_w - margin[0], vi.current_h - margin[1])
    for m in modes:
      if m[0] <= target[0] and m[1] <= target[1]:
        if DEBUG: print('Display resolution:', m)
        return m
  return (0,0)

def main(argv):
  print("Initializing...")
  pygame.display.set_caption("Squareworld")

  #screen = pygame.display.set_mode((1536,800))
  screen = pygame.display.set_mode(ChooseVideoMode(), pygame.RESIZABLE)
  if DEBUG:
    if screen.get_flags() & pygame.HWACCEL: print("screen is HARDWARE ACCELERATED!")
    if screen.get_flags() & pygame.HWSURFACE: print("screen is in video memory")
  icon = pygame.image.load('icons/nested-squares-icon.png')
  pygame.display.set_icon(icon)
  #pygame.key.set_repeat(100, 100)

  world = World()
  global manager
  manager = WindowManager(text='manager')
  appWnd = AppWnd(manager, screen, world, text='appWnd')

  #monofont = pygame.font.SysFont('freemono',16,bold=True)
  #font_test_img = monofont.render('MWQj|_{}[]', False, (0,0,0))
  #print('freemono 16 is {} px high'.format(font_test_img.get_height()))
  #assert font_test_img.get_height() == 17

  print("Ready.")

  clock = pygame.time.Clock()
  target_fps = 60
  elapsed = target_fps
  dt_std = SECOND // target_fps  # 1000/16 = 17+2/3
  dt = dt_std
  clock.tick() # Start measuring frames from now, not from when pygame was initialized.
  quit = False
  while not quit:
    # Process events
    for evt in pygame.event.get():
      if evt.type is pygame.QUIT:
        quit = True
      elif evt.type is pygame.KEYDOWN:
        if evt.key is pygame.K_q and evt.mod & pygame.KMOD_CTRL:
          quit = True
        elif not manager.OnEvent(evt):
          DebugKeystrokeEvent(evt)
      elif evt.type is pygame.VIDEORESIZE:
        # VIDEORESIZE is not reliably sent under Linux
        #print('event VIDEORESIZE {}'.format(evt))
        assert evt.size[0] == evt.w and evt.size[1] == evt.h
        screen = pygame.display.set_mode(evt.size, pygame.RESIZABLE)
        manager.Resize(pygame.Rect((0,0),evt.size))
        appWnd.Resize(pygame.Rect((0,0),evt.size))
      else:
        manager.OnEvent(evt)
    # Update state
    world.Update(dt)
    #if world.changed:
    #  print('world changed')
    #  appWnd.Dirty()
    # Update screen
    dirtyList = manager.RenderDirtyNow(screen)
    if dirtyList:
      label_text = '{:4d}x{:<4d}, {:4d} ms, {:3d} fps'.format(screen.get_width(), screen.get_height(), dt, SECOND//elapsed)
      fps_label = manager.GetFont('LABEL').render(label_text, False, (255,255,0))
      screen.blit(fps_label, ( screen.get_width() - fps_label.get_width()
                             , screen.get_height() - fps_label.get_height()
                             ))
      world.player.Changed(False)
      world.Changed(False)
      pygame.display.update(dirtyList)
    assert not (world.changed or world.player.changed)
    elapsed = clock.tick(target_fps)
    # On next timeslice, compensate for actual elapsed time.
    dt = elapsed  # dt_std + (dt_std - elapsed)
    #print('elapsed = {} ms, dt = {} ms'.format(elapsed,dt))

if __name__=='__main__':
  if '--debug' in sys.argv:
    DEBUG = True
    windowing._DEBUG = True
  pygame.init()
  pygame.mixer.quit()  # stop pygame 100% CPU bug circa 2017-2018
  try:
    if '--profile' in sys.argv:
      import cProfile
      cProfile.run('main(sys.argv)', sort='cumulative')
    else:
      main(sys.argv)
  finally:
    pygame.quit()

