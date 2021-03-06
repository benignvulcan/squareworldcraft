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

import sys, enum, math, random, itertools, glob, csv, argparse

#import numpy as np
import pygame

import windowing
from windowing import *

_DEBUG = False
def IFDEBUG(value):
  if _DEBUG: return value
  else: return None
def BUGPRINT(fmtstr, *posargs, **kwargs):
  if _DEBUG: print(fmtstr.format(*posargs, **kwargs))

SECOND = 1000  # conversion factor from seconds to standard units (miliseconds)

manager = None

def ceildiv(n, d):  # numerator or dividend, denominator or divisor
  'Integer division, but rounding up.'
  return (n + (d-1)) // d

def ManhattanDistance(p, q):
  "Return the distance between p and q if you can only move horizontally or vertically."
  return abs(q[0]-p[0])+abs(q[1]-p[1])

def ChessboardDistance(p, q):
  # A.K.A. Chebyshev distance.
  "Return the distance between p and q if you can only move horizontally, vertically, or on a 45 degree diagonal."
  return max( abs(p[0]-q[0]), abs(p[1]-q[1]) )

class Thing:

  def __init__(self):
    pass

  def BaseIconName(self):
    return self.__class__.__name__  # name used to match the filename of the icon image ("Pickaxe")
  def DisplayName(self):
    return self.__class__.__name__  # "Steel Pickaxe", "Water"
  def SymbolName(self):
    return ''                       # short chemical symbol string ("Cu" or "H₂O"), if desired

  color_rgb = (255,0,255)
  color_hsv = (300,100,100)
  hardness = 1
  density = 1000
  meltingpoint = None
  boilingpoint = None
  flametempmin = None
  flametempmax = None
  stacksize = 999

  def GetColor(self): return HSV2RGB(self.color_hsv)

  icon_cache = {}

  @classmethod
  def FlushIconCache(cls):
    cls.icon_cache = {}

  def LoadIcon(self):
    # TODO:
    #  walk up the inheritance tree for names
    #  use fnmatch?
    name = self.BaseIconName()
    if name in Thing.icon_cache:
      return Thing.icon_cache[name]
    for filename in glob.glob('icons/'+name.lower()+'.png'):
      icon = pygame.image.load(filename)
      Thing.icon_cache[name] = icon
      return icon
    return None

  def GetIcon(self, size=(64,64)):
    key = (self, (size[0],size[1]))
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
        if self.SymbolName():
          txt_img = pygame.font.SysFont('freemono', size[1]//2, bold=True).render(self.SymbolName(), True, (0,0,0))
          sym_img = pygame.Surface( (txt_img.get_width()+4, txt_img.get_height()+4), pygame.SRCALPHA )
          sym_img.blit(txt_img, ( 0, 2))
          sym_img.blit(txt_img, ( 4, 2))
          sym_img.blit(txt_img, ( 2, 0))
          sym_img.blit(txt_img, ( 2, 4))
          txt_img.fill( (255,255,255), special_flags=pygame.BLEND_MAX )
          sym_img.blit(txt_img, ( 2, 2))
          sym_img.fill( (255,255,255,127), None, pygame.BLEND_RGBA_MULT)
          img.blit(sym_img, (img.get_width()//2-sym_img.get_width()//2, img.get_height()//2-sym_img.get_height()//2))
      Thing.icon_cache[key] = img
    return Thing.icon_cache[key]

  def IsTraversable(self): return False
  def WouldHarvestUsing(self, tool): return (0,None)
  def IsWorkstation(self): return False
  def IsPickUpAble(self): return False
  def IsPlaceable(self): return False

  def UseDuration(self):
    'Time (in ms) it takes to use/swing this tool once'
    return SECOND*2
  def PowerEfficiency(self):
    'For a given power input (such as 100 W), what percent produces useful work with this tool?'
    return 10  # percentage
    # Active humans need about 2400 to 3000 food calories (=8,368,000 to 12,552,000 joules) per day.
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

  def __new__(cls, *posargs, **kwargs):
    key = (cls,) + posargs + tuple(sorted(kwargs.items()))
    if not key in FlyweightThing.instances:
      # Oddly, object.__new__() doesn't call cls.__init__()
      # But it does complain about excess arguments (if cls.__init__ is not explicitly defined).
      # (Apparently cls.__call__() calls cls.__init__())
      # So little is lost by discarding args to derived class ctors.
      FlyweightThing.instances[key] = super(FlyweightThing, cls).__new__(cls)
    return FlyweightThing.instances[key]

class Terrain(FlyweightThing):
  'Terrain is what is left when a cell is bare empty'
class TerrainWater(Terrain):
  def GetColor(self): return (0,0,127)
class TerrainSaltWater(TerrainWater):
  pass
class TerrainLand(Terrain):
  def IsTraversable(self): return True
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

class Water(FlyweightThing): pass

class Situatable(FlyweightThing):
  def __init__(self, *posargs, inSitu=False, **kwargs):
    super().__init__(*posargs, **kwargs)
    self._inSitu = inSitu
  def InSitu(self): return self._inSitu
  def BaseIconName(self):
    name = super().BaseIconName()
    if self._inSitu:
      name += 'Situ'
    return name
  def IsTraversable(self): return not self._inSitu
  def EnergyToHarvest(self):
    if self._inSitu:
      return 500
    else:
      return 10

class Harvestable(Situatable):
  def WouldHarvestUsing(self, tool):
    something = (1, self.__class__())   # this is not the thing that is there, this is the thing it would become!
    nothing = (0, None)
    if not self._inSitu:
      return something
    if isinstance(tool, (Hammer, Pickaxe)):
      if tool.HarvestingMagnitude() >= self.hardness:
        return something
    return nothing

class PickUpAble(Harvestable):
  def IsPickUpAble(self): return True

class Placeable(Thing):
  def IsPlaceable(self): return True

class Rock(PickUpAble, Placeable): pass
class Ore(PickUpAble, Placeable): pass
class Metal(PickUpAble, Placeable):
  _symbolName = ''
  def SymbolName(self): return self._symbolName
class Alloy(Metal): pass
class Gem(PickUpAble, Placeable): pass
class Plant(Harvestable):
  def WouldHarvestUsing(self, tool):
    if (self._inSitu and isinstance(tool, Woodaxe)) or not self._inSitu:
      return (1, self.__class__())
    else:
      return (0,None)

class Stone(Rock): pass

assert Stone() is Stone()
assert Stone(inSitu=True) is Stone(inSitu=True)
assert Stone() != Stone(inSitu=True)
assert Stone(inSitu=False) != Stone(inSitu=True)
assert Stone(inSitu=False) != Stone()
BUGPRINT('{} {} {}', Stone().DisplayName(), Stone(inSitu=True).DisplayName(), Stone(inSitu=False).DisplayName())
assert Stone().DisplayName() == 'Stone'
assert Stone(inSitu=True).DisplayName() == 'Stone'
assert Stone(inSitu=False).DisplayName() == 'Stone'
BUGPRINT('{} {} {}', Stone().BaseIconName(), Stone(inSitu=True).BaseIconName(), Stone(inSitu=False).BaseIconName())
assert Stone().BaseIconName() == 'Stone'
assert Stone(inSitu=True).BaseIconName() == 'StoneSitu'
assert Stone(inSitu=False).BaseIconName() == 'Stone'

class Clay(PickUpAble, Placeable):
  color_hsv = (20,50,40)

class Cassiterite(Ore): pass
class Tin(Metal):
  _symbolName = 'Sn'

class Malachite(Ore): pass
class Copper(Metal):
  _symbolName = 'Cu'

class NativeSilver(Ore): pass
class Silver(Metal):
  _symbolName = 'Ag'

class NativeGold(Ore): pass
class Gold(Metal):
  _symbolName = 'Au'

class NativeAluminum(Ore): pass
class Aluminum(Metal):
  _symbolName = 'Al'

class Bismuthinite(Ore): pass
class Bismuth(Metal):
  _symbolName = 'Bi'

class Garnierite(Ore): pass
class Nickel(Metal):
  _symbolName = 'Ni'

class NativePlatinum(Ore): pass
class Platinum(Metal):
  _symbolName = 'Pt'

class Sphalerite(Ore): pass
class Zinc(Metal):
  _symbolName = 'Zn'
class Tetrahedrite(Ore): pass
class Brass(Alloy): pass  # copper + zinc; often 2/3 copper + 1/3 zinc
class Bronze(Alloy): pass # modern standard bronze is 88% copper + 12% tin
class Electrum(Alloy): pass # silver+gold
class Steel(Alloy): pass  # iron with up to 1.7% carbon
class Flint(Rock): pass
class Diamond(Gem): pass
class Hematite(Ore): pass
class Limonite(Ore): pass
class Magnetite(Ore): pass
class Iron(Metal):
  _symbolName = 'Fe'
class Galena(Ore): pass
class Lead(Metal):
  _symbolName = 'Pb'

class Wood(Plant, PickUpAble, Placeable): pass
class Grass(Plant):
  def GetColor(self): return (0,127,0)
class Vine(Plant, PickUpAble, Placeable):
  def GetColor(self): return (0, 191, 0)

class OfMaterial(Thing):
  def __init__(self, material, *posargs, **kwargs):
    super().__init__(*posargs, **kwargs)
    self._material = material
  def Material(self): return self._material
  def GetColor(self): return self._material.GetColor()
  def DisplayName(self):
    return '{} {}'.format(self._material.DisplayName(), super().DisplayName())

class Tool(Thing): pass
class Component(Thing): pass
class Hands(Tool):
  'Dummy tool for when no tool is used'
class Pickaxe(Tool, OfMaterial):
  def HarvestingMagnitude(self):
    return self._material.hardness + .5
  def PowerEfficiency(self):
    return max(10, self._material.hardness * 8)
class Woodaxe(Tool, OfMaterial):
  pass
class AxeHead(Component, OfMaterial): pass
class PickaxeHead(Component, OfMaterial): pass
class Hammer(Tool, OfMaterial):
  def HarvestingMagnitude(self):
    return self._material.hardness

# TODO:
#   Clay --[Furnace]--> Ceramic Bowl/Crucible
#   Sand + Clay --[Furnace]--> Bricks
#   Sand + Clay --[Furnace]--> Mold(Anvil)
#   Bloomery - the earliest sort of smelting furnace
#   Forge - a better open fire, using coal/coke/charcoal, bellows, tuyere & hearth
#   Metal + Mold(Anvil) --[Forge?]--> Anvil
#   Metal --[Anvil+Forge?]-> PickaxeHead
#   Shovel (faster than Hands)
#   Crucible ?

class Charcoal(PickUpAble, Placeable):
  pass
class Coke(PickUpAble, Placeable):
  pass
class Brick(PickUpAble, Placeable):
  color_hsv = (20,85,80)
  # A regular (non "firebrick") brick can withstand temperatures up to about 1200f (=992K)
class FireBrick(PickUpAble, Placeable):
  color_hsv = (20,25,95)
  # Withstands temperatures up to around 1800f (=1255K)

class Workstation(Placeable):
  def IsWorkstation(self): return True
class CampFire(Workstation):
  color_hsv = (20,100,100)
class StoneFurnace(Workstation):
  color_hsv = (0,0,50)
class BrickFurnace(Workstation):
  color_hsv = Brick.color_hsv
class FireBrickFurnace(Workstation):
  color_hsv = FireBrick.color_hsv
class Table(Workstation):
  def GetColor(self): return (204,150,86)

def LoadMaterialsProperties():
  with open('materials_properties.csv', newline='') as f:
    attributes = []
    sheet = csv.reader(f)
    row = next(sheet)    # get the header row
    for cell in row:
      assert isinstance(cell, str)
      assert cell.isidentifier() or cell.startswith('#')
      attributes.append(cell)
    BUGPRINT('attributes = {}', attributes)
    for row in sheet:
      if len(row) < 2:
        continue
      klassname = row[0]
      assert isinstance(klassname, str)
      if not klassname.isidentifier():
        continue
      if not klassname in globals():
        print('WARNING: class "{}" not defined'.format(klassname))
        continue
      klass = globals()[klassname]
      assert isinstance(klass, type)
      #print(klass)
      for i in range(1,len(row)):
        assert i < len(attributes)
        attr = attributes[i]
        value = row[i]
        if not value or value.isspace() or value.startswith('#'):
          continue
        if attr in ('color', 'color_rgb', 'color_hsv'):
          value = tuple(map(int, value.split(',')))
          assert len(value) == 3
        else:
          if value.isdigit():
            value = int(value)
          else:
            value = float(value)
        assert not attr in vars(klass)
        BUGPRINT('{}.{} = {}', klassname, attr, value)
        setattr(klass, attr, value)

CARDINAL_DIRECTIONS = ( (0,-1), (1,0), (0,1), (-1,0) )

class AnimateThing(Observable, Thing):

  color_hsv = (0,100,100)

  @classmethod
  def InitClassConstants(cls):
    cls.SPEED_MIN = 0.25 / SECOND   # tiles/sec of movement speed
    cls.SPEED_MAX = 4.00 / SECOND

    # Energy here is effectively "number of milliseconds to live".
    # It is expended (by living creatures) at the following baseline rate:
    cls.ENERGY_EXPENDITURE_BASELINE = 1 * SECOND//SECOND  # 1 per ms

    cls.DIGESTION_EFFICIENCY = 0.1
    cls.DIGESTION_INEFFICIENCY = int(1.0 / cls.DIGESTION_EFFICIENCY)

    # Minimum viable energy is effectively the energy a Carnivore gets
    # (times inefficiency) from the corpse of an animal that died of starvation.
    cls.ENERGY_MINIMUM_VIABLE = cls.DIGESTION_INEFFICIENCY * cls.ENERGY_EXPENDITURE_BASELINE * 120 * SECOND

    print('ENERGY_MINIMUM_VIABLE = {}'.format(cls.ENERGY_MINIMUM_VIABLE))

  def __init__(self, world, initialpos, *posargs, energy=None, **kwargs):
    super().__init__(*posargs, **kwargs)
    self.world = world
    self.pos = [initialpos[0], initialpos[1]]
    if energy is None:
      energy = self.ENERGY_MINIMUM_VIABLE
    self.energy = energy
    self.age = 0
    self.Changed()

  def Changed(self, changed=True):
    self.changed = changed
    if changed:
      self.NotifyChange()

  def IsAlive(self):
    return self.energy >= self.ENERGY_MINIMUM_VIABLE

  def GetColor(self):
    c = super().GetColor()
    if not self.IsAlive():
      c = (c[0]//4, c[1]//4, c[2]//4)
    return c

  def CanOccupy(self, newpos):
    'Return True if self can be at the given position.'
    if newpos[0] < 0 or newpos[1] < 0 or newpos[0] >= self.world.sz[0] or newpos[1] >= self.world.sz[1]:
      return False
    terrain = self.world.ground[newpos[1]][newpos[0]]
    numthing, thing = self.world.ThingsAt(newpos)
    if terrain.IsTraversable() and (numthing==0 or thing is None or thing.IsTraversable()):
      return True
    return False

  def MoveTo(self, newpos):
    'Unconditionally move self to newpos - assumes CanOccupy() was already consulted.'
    self.pos[0] = newpos[0]
    self.pos[1] = newpos[1]
    self.Changed()

  def Update(self, dt):
    self.age += dt

AnimateThing.InitClassConstants()

class Animal(AnimateThing):

  def __init__(self, *posargs, **kwargs):
    super().__init__(*posargs, **kwargs)
    self.walkingTimeout = 0  # Time to wait until next walking can be performed
    self.walkingDirection = (random.randrange(3)-1,random.randrange(3)-1)
    self.speed = random.uniform(self.SPEED_MIN, self.SPEED_MAX)

  def FindNearestTargetPoints(self, targetFilter, radius=20):
    'Return a tuple of the nearest (and therefore equidistant) points of interest'
    targets = []
    # Include Player?
    if ManhattanDistance(self.pos, self.world.player.pos) <= radius and targetFilter(self.world.player):
      targets.append(tuple(self.world.player.pos))
    # Find all animals in range
    for p in self.world.animals.keys():
      if ManhattanDistance(self.pos, p) <= radius:
        for a in self.world.animals[p]:
          if not a is self and targetFilter(a):
            targets.append(p)
    if targets:
      # Find nearest of the nearby targets
      targets.sort(key=lambda p: ManhattanDistance(self.pos, p))
      nearest = ManhattanDistance(self.pos, targets[0])
      nearestTargets = itertools.takewhile(lambda p: ManhattanDistance(self.pos,p)==nearest, targets)
      if nearestTargets:
        targets = nearestTargets
    return tuple(targets)

  def PickWalk(self, points):
    # Usually walk in same direction, if possible
    pt = (self.pos[0]+self.walkingDirection[0], self.pos[1]+self.walkingDirection[1])
    if not (pt in points and random.randrange(5)):
      # Sometimes walk randomly
      pt = random.choice(points)
    return pt

  def UpdateWalking(self, dt):
    self.walkingTimeout -= dt
    if self.walkingTimeout < 0:
      self.walkingTimeout = 0
    if self.walkingTimeout <= 0 and self.energy >= self.ENERGY_MINIMUM_VIABLE:
      choices = [tuple(self.pos)]
      for d in CARDINAL_DIRECTIONS:
        pt = (self.pos[0]+d[0], self.pos[1]+d[1])
        if self.CanOccupy(pt):
          choices.append(pt)
      if choices:
        pt = self.PickWalk(choices)
        self.walkingDirection = (pt[0]-self.pos[0], pt[1]-self.pos[1])
        self.MoveTo(pt)
        assert self.speed > 0.0
        self.walkingTimeout += int(1.0 / self.speed)

  def Update(self, dt):
    if self.energy < self.ENERGY_MINIMUM_VIABLE:
      return
    self.UpdateWalking(dt)  # may consume food as side-effect
    self.energy -= dt * self.ENERGY_EXPENDITURE_BASELINE
    super().Update(dt)
    if self.energy < self.ENERGY_MINIMUM_VIABLE:
      print('{} died @ {}, aged {}s, with {} energy'.format(
                self.__class__.__name__, self.pos, self.age / SECOND, self.energy))
    elif self.energy >= self.energy_reproduction:
      self.energy -= self.energy_reproduction // 2
      child = self.__class__(self.world, self.pos, energy=self.energy_reproduction // 2)
      child.speed = self.speed
      self.world.AddAnimal(child)
      print('{} born @ {} with {} energy'.format(self.__class__.__name__, self.pos, child.energy))

class Herbivore(Animal):
  color_hsv = (90,100,50)

  def __init__(self, *posargs, **kwargs):
    super().__init__(*posargs, **kwargs)
    self.energy_safety_margin = self.ENERGY_EXPENDITURE_BASELINE * 30 * SECOND
    self.energy += self.energy_safety_margin
    self.energy_reproduction = self.energy * 2

  def PickWalk(self, points):
    # Eat what's here, then do regular walk.
    numthing, thing = self.world.ThingsAt(self.pos)
    if numthing and isinstance(thing, (Grass,Vine)):
      self.world.SetThingsAt(self.pos, (0,None))
      self.energy += 20 * SECOND
    # Move away from player and Carnivores, if possible
    nearestPredators = self.FindNearestTargetPoints(lambda t: isinstance(t, (Carnivore,Player)))
    if nearestPredators:
      # Evaluate dangerousness of each move
      metrics = [ (sum(ManhattanDistance(p,q) for q in nearestPredators)/len(nearestPredators), p) for p in points ]
      metrics.sort(reverse=True)
      # Sigh. Failing to immediately force the output of takewhile() results in it attempting to
      # evaulate `metrics` later after `metrics` has been re-bound to an incompatible value!
      betterMetrics = tuple(itertools.takewhile(lambda t: t[0]==metrics[0][0], metrics))
      if betterMetrics:
        metrics = betterMetrics  # some were less dangerous, so go one of those directions
      points = tuple(t[1] for t in metrics)
    return super().PickWalk(points)

class Carnivore(Animal):
  color_hsv = (30,75,75)

  def __init__(self, *posargs, **kwargs):
    super().__init__(*posargs, **kwargs)
    self.energy_safety_margin = self.ENERGY_EXPENDITURE_BASELINE * 120 * SECOND
    self.energy += self.energy_safety_margin
    self.energy_reproduction = self.energy * 2
    # For now:
    #   * Carnivores have much less plentiful food
    #   * But are faster than Herbivores
    self.speed *= 1.5

  def PickWalk(self, points):
    # Eat some of what's here, then do regular walk.
    for a in tuple(self.world.animals.get(tuple(self.pos),[])):
      if isinstance(a, Herbivore) or (isinstance(a,Carnivore) and not a.IsAlive()):
        if a.IsAlive():
          wasAlive = 'live'
        else:
          wasAlive = 'dead'
        acquired_energy = a.energy // 10
        a.energy = 0
        self.energy += acquired_energy
        self.world.RemoveAnimal(self.pos, a)
        print('{} {} eaten @ {} for {} energy'.format(wasAlive, a.__class__.__name__, self.pos, acquired_energy))
        break
    # Move toward player and Herbivores, if possible
    nearestPrey = self.FindNearestTargetPoints(lambda t: isinstance(t, (Herbivore,Player) or not t.IsAlive()))
    if nearestPrey:
      # Evaluate attractiveness of each move
      metrics = [ (sum([ManhattanDistance(p,q) for q in nearestPrey])/len(nearestPrey), p) for p in points ]
      metrics.sort()
      betterMetrics = tuple(itertools.takewhile(lambda t: t[0]==metrics[0][0], metrics))
      if betterMetrics:
        metrics = betterMetrics  # some were more attractive, so go in one of those directions
      points = tuple(t[1] for t in metrics)
    return super().PickWalk(points)

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

class Player(AnimateThing):

  WIELD_TOOL = 1
  WIELD_MATERIAL = 2

  def __init__(self, world, initialpos=(10,10), **kwargs):
    super().__init__(world, initialpos, **kwargs)
    #self.world = world
    #self.pos = [initialpos[0], initialpos[1]]
    self.inventory = [ [0,None] for i in range(40) ]
    self.inventory_selection = 0  # first item
    self.walkingSpeed = SECOND//6
    self.walkingTimeout = 0  # Time to wait until next walking can be performed
    self.walkingQueue = []   # Direction(s) to try to walk in - most recent first
    self.wieldType = None
    self.wieldPos = None
    self.throb = None   # None, or current position in throb cycle
    self.Changed()

  def PowerProduction(self): return 100  # in watts (a.k.a. joules/sec)

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
      print("Got {} {}".format(some_thing[0], some_thing[1].DisplayName()))
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
        print("Dropped {} {}".format(count, some_thing[1].DisplayName()))
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
      nameLabel = manager.GetFont('LABEL').render(thing.DisplayName(), True, (0,0,0))
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

  def MoveTo(self, newpos):
    'Unconditionally move player to newpos - assumes CanOccupy() was already consulted.'
    if not self.wieldPos is None:
      self.wieldPos = ( self.wieldPos[0] + newpos[0] - self.pos[0]
                      , self.wieldPos[1] + newpos[1] - self.pos[1] )
    super().MoveTo(newpos)
    #print('player pos = {}'.format(self.pos))

  def CanUseAt(self, tool, hitpos):
    pass

  def WouldHarvestAt(self, hitpos):
    numtool, tool = self.SelectedInventory()
    if ChessboardDistance(hitpos, self.pos) <= 1:
      numtarget, target = self.world.ThingsAt(hitpos)
      if numtarget:
        (n,t) = target.WouldHarvestUsing(tool)
        return (n*numtarget, t)
    return (0,None)

  def UsePrimaryAt(self, hitpos):
    numthing, thing = self.WouldHarvestAt(hitpos)
    if numthing and not thing is None:
      self.world.SetThingsAt(hitpos, (0,None))
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
    print('OnUsePrimaryBegin')
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
          self.walkingTimeout += self.walkingSpeed
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
      if self.wieldType is Player.WIELD_TOOL:
        wouldNumThing, wouldThing = self.WouldHarvestAt(self.wieldPos)
        if wouldNumThing and not wouldThing is None:
          progress = self.world.progress.get(self.wieldPos, 0)
          numThing, thing = self.world.ThingsAt(self.wieldPos)
          BUGPRINT('{} progress out of {} EnergyToHarvest', progress, thing.EnergyToHarvest())
          if progress >= thing.EnergyToHarvest():
            self.UsePrimaryAt(self.wieldPos)
          else:
            if held is None:
              held = Hands()
            j = dt * held.PowerEfficiency() // 100
            self.world.progress[self.wieldPos] = progress + j
            self.world.Changed()
      elif self.wieldType is Player.WIELD_MATERIAL and numheld and not held is None:
        numtarget, target = self.world.ThingsAt(self.wieldPos)
        if numtarget == 0 and numheld and ChessboardDistance(self.wieldPos, self.pos) == 1:
          if held.IsPlaceable():
            (numremoved, removed) = self.RemoveInventory( (1,held), self.inventory_selection )
            if numremoved:
              self.world.SetThingsAt(self.wieldPos, (numremoved, removed))
              self.world.Changed()

  def Update(self, dt):
    self.UpdateWalking(dt)
    self.UpdateWielding(dt)

class World(Observable):
  # Containing the terrain, player, inventory, etc.

  def __init__(self, *posargs, **kwargs):
    super().__init__(*posargs, **kwargs)
    self.sz = (1000,1000)
    self.area = self.sz[0]*self.sz[1]
    grass_flyweight = TerrainGrass()  # avoiding the ctor call significantly speeds this up
    #row_prototype = [ grass_flyweight for r in range(self.sz[1]) ]
    #self.ground = [ row_prototype[:] for c in range(self.sz[0]) ]
    self.ground = [ [ grass_flyweight for r in range(self.sz[1]) ] for c in range(self.sz[0]) ]
    #self.ground = np.random.randint(0,4,self.sz)
    self.lighting = [ [True]*self.sz[0] for r in range(self.sz[1]) ]
    self.things = [ [ (0,None) for r in range(self.sz[1]) ] for c in range(self.sz[0]) ]
    self.progress = {}  # map from (x,y) to milliseconds remaining to finish choping/pickaxing/harvesting Thing
    self.animals = {}   # map from (x,y) to list of animals
    self.player = Player(self)
    self.icons = {}
    print('{:,} cells'.format(self.sz[0]*self.sz[1]))
    self.player.Subscribe(CHANGE, self.OnChange)
    self.Changed()

  def Generate(self, progressCallback):
    self.GenerateTerrain(progressCallback)
    progressCallback(75)
    self.GenerateThings()
    progressCallback(80)
    self.GenerateClay()
    self.GenerateRock()
    self.GenerateAnimals()
    progressCallback(90)

  def GenerateTerrain(self, progressCallback):
    # Assuming ground[] is already just Grass
    p = 5
    plots = self.area // 10000
    for value in (TerrainSand(), TerrainWater()):
      for i in range(plots):
        width = random.randrange(12,64)
        height = random.randrange(12,64)
        top = random.randrange(self.sz[1] - height)
        left = random.randrange(self.sz[0] - width)
        r = pygame.Rect(left, top, width, height)
        self.GroundFill(r, value)
        p += 70/(2*plots)
        progressCallback(int(p))

  def GenerateThings(self):
    count = self.area // 400
    for i in range(count):
      self.things[random.randrange(self.sz[1])][random.randrange(self.sz[0])] = (1,Stone())
    for i in range(count):
      self.things[random.randrange(self.sz[1])][random.randrange(self.sz[0])] = (1,Wood())
    for i in range(count):
      self.things[random.randrange(self.sz[1])][random.randrange(self.sz[0])] = (1,Vine())
    for i in range(count*100):
      self.things[random.randrange(self.sz[1])][random.randrange(self.sz[0])] = (1,Grass())
    for i in range(count):
      self.things[random.randrange(self.sz[1])][random.randrange(self.sz[0])] = \
        (random.randrange(4)+random.randrange(3)+1, Wood(inSitu=True))

  def GenerateClay(self):
    for i in range(self.area // 50000):
      width = random.randrange(12,64)
      height = random.randrange(12,64)
      top = random.randrange(self.sz[1] - height)
      left = random.randrange(self.sz[0] - width)
      r = pygame.Rect(left, top, width, height)
      self.ThingFill(r, (1, Clay(inSitu=True)))
      self.LightFill(r.inflate(-4,-4), False)

  def GenerateRock(self):
    for i in range(self.area // 5000):
      width = random.randrange(12,128)
      height = random.randrange(12,128)
      top = random.randrange(self.sz[1] - height)
      left = random.randrange(self.sz[0] - width)
      r = pygame.Rect(left, top, width, height)
      self.ThingFill(r, (2, Stone(inSitu=True)))
      self.LightFill(r.inflate(-4,-4), False)
      ores = list(ore for ore, count in 
        { Bismuthinite : 3
        , Cassiterite : 2
        , Galena : 3
        , Garnierite : 3
        , Hematite : 3
        , Limonite : 3
        , Magnetite : 3
        , Malachite : 3
        , NativeAluminum : 5
        , NativeGold : 1
        , NativePlatinum : 1
        , NativeSilver : 2
        , Sphalerite : 3
        , Tetrahedrite : 4
        }.items() for rep in range(count))
      for j in range(width*height//120):
        self.GenerateVein(r, (1, random.choice(ores)(inSitu=True)) )

  def GenerateVein(self, rect, value, maxSize=12):
    stone = Stone(inSitu=True)
    points = [(random.randrange(rect.left, rect.right), random.randrange(rect.top, rect.bottom))]
    p = points[0]
    for i in range(random.randrange(maxSize)):
      p2 = (p[0]+random.randrange(-1,2), p[1]+random.randrange(-1,2))
      if self.CollidePoint(p2) and self.things[p2[1]][p2[0]][1] == stone and not p2 in points:
        points.append(p2)
        p = p2
    for p in points:
      self.things[p[1]][p[0]] = value

  def GenerateAnimals(self):
    for i in range(800):
      p = ( random.randrange(self.sz[0]), random.randrange(self.sz[1]) )
      numthing, thing = self.things[p[1]][p[0]]
      if numthing and not thing is None:
        if not thing.IsTraversable():
          continue
      if random.randrange(4):
        a = Herbivore(self,p)
      else:
        a = Carnivore(self,p)
      self.AddAnimal(a)
    print('{} animals created'.format(len(self.animals)))

  def AddAnimal(self, a):
    self.animals.setdefault(tuple(a.pos), []).append(a)
    a.Subscribe(CHANGE, self.OnChange)

  def RemoveAnimal(self, p, a):
    p = tuple(p)
    self.animals[p].remove(a)
    if not self.animals[p]:
      del self.animals[p]

  def Changed(self, changed=True):
    self.changed = changed
    if self.changed:
      self.NotifyChange()

  def OnChange(self, evt):
    self.Changed()

  def CollidePoint(self, p):
    'Is cell at coordinate p in the world?  (Or does it fall off the edge?)'
    return not( p[0] < 0 or p[1] < 0 or p[0] >= self.sz[0] or p[1] >= self.sz[1] )

  def IterRect(self, aRect):
    'Return an iterator over coordinates on the map'
    r = pygame.Rect((0,0),self.sz).clip(aRect)
    for row in range(r.top, r.bottom):
      for col in range(r.left, r.right):
        yield (col,row)

  def IterRectAround(self, p, radius):
    'Return an iterator over coordinates on the map'
    return self.IterRect((p[0]-radius,p[1]-radius,radius+radius+1,radius+radius+1))

  def GroundFill(self, r, value):
    for row in range(r.height):
      for col in range(r.width):
        self.ground[r.top+row][r.left+col] = value
    self.Changed()

  def LightFill(self, r, value):
    for row in range(r.height):
      for col in range(r.width):
        self.lighting[r.top+row][r.left+col] = value
    self.Changed()

  def ThingFill(self, r, value):
    for row in range(r.height):
      for col in range(r.width):
        self.things[r.top+row][r.left+col] = value
    self.Changed()

  def FindEmptySpotNear(self, p, max_radius=99):
    for radius in range(max_radius):
      for row in range(p[1]-radius,p[1]+1+radius):
        if row < 0 or row >= self.sz[1]:
          continue
        for col in range(p[0]-radius,p[0]+1+radius):
          if col < 0 or col >= self.sz[0]:
            continue
          if not self.ground[row][col].IsTraversable():
            continue
          (numthing, thing) = self.things[row][col]
          if numthing and not thing.IsTraversable():
            continue
          return (col,row)
    return None

  def MovePlayerToEmptySpot(self):
    p = self.FindEmptySpotNear(self.player.pos)
    if not p is None:
      self.player.MoveTo(p)

  def Update(self, dt):
    self.player.Update(dt)
    # Animals can move or die during this loop.
    for p in tuple(self.animals.keys()):
      for a in tuple(self.animals[p]):
        if p in self.animals and a in self.animals[p]:
          self.animals[p].remove(a)
          a.Update(dt)
          self.animals.setdefault(tuple(a.pos),[]).append(a)
      if p in self.animals and not self.animals[p]:
        del self.animals[p]
    self.GrowPlants(dt)

  def GrowPlants(self, dt):
    if random.randrange(SECOND//2) < dt: # about once per second//2
      p = (random.randrange(self.sz[1]), random.randrange(self.sz[0]))
      numthing, thing = self.things[p[1]][p[0]]
      if numthing == 0 and thing is None:
        self.things[p[1]][p[0]] = (1,Grass())
        print('new grass at {}'.format(p))

  def ThingsAt(self, p):
    return self.things[p[1]][p[0]]
  def SetThingsAt(self, p, something):
    self.things[p[1]][p[0]] = something
    self.ExposeToLight(p)
  def ExposeToLight(self, p, r=2):
    for q in self.IterRectAround(p,r):
      self.lighting[q[1]][q[0]] = True

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
    #for (col,row) in self.world.IterRect((self.world_col_start,self.world_row_start,half_scr_cols*2,half_scr_rows*2)):
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
        elif not self.world.lighting[row][col]:
          pygame.draw.rect(surf, (0,0,0), r)
        else:
          terrain = self.world.ground[row][col]
          pygame.draw.rect(surf, terrain.GetColor(), r)
          numthing, thing = self.world.ThingsAt((col,row))
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
          if (col,row) in self.world.animals:
            for a in self.world.animals[(col,row)]:
              #c = (255,63,0)
              c = a.GetColor()
              radius = self.tilesize * 3 // 12
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
      print('player.pos = {}'.format(self.world.player.pos))
      nHerb = 0
      nCarni = 0
      nDead = 0
      for p in self.world.animals:
        for a in self.world.animals[p]:
          if not a.IsAlive():
            nDead += 1
          elif isinstance(a, Herbivore): nHerb += 1
          elif isinstance(a, Carnivore): nCarni += 1
          else: assert False
      print('{} animals = {} herbivores + {} carnivores + {} dead'.format(nHerb+nCarni+nDead, nHerb, nCarni, nDead))
    return False

  def OnKeyUp(self, evt):
    if evt.key in keyToWalkDirection:
      self.player.OnWalkEnd( keyToWalkDirection[evt.key] )
      return True
    elif evt.key in keyToActDirection:
      self.player.OnUsePrimaryEnd()
      return True
    return False

class HotbarSlot(Button):

  def OnChange(self, evt):
    self.image = self.player.GetInventoryImage(self.idx, size=self.rect.width)
    self.Selected(self.idx == self.player.inventory_selection)
    self.Dirty()

class HotbarWnd(Window):

  HOTBAR_ENTRIES = 10
  MARGIN = 2
  BUTTON_MAX_SIZE = 64
  BODY_COLOR = HSV2RGB((30,10,80))
  FRAME_COLOR = HSV2RGB((30,20,70))
  SELECTION_COLOR = HSV2RGB((60,40,90))

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
    BUGPRINT('HotbarWnd.OnClick({}), id={}', evt, evt.sender.idx)
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

class CatalystsPanel(Window):

  def __init__(self, parent, world, **kwargs):
    super().__init__(parent, **kwargs)
    self.world = world
    self.catalystThings = []
    self.size = 64
    self.world.Subscribe(CHANGE, self.OnChange)
    self.world.player.Subscribe(CHANGE, self.OnChange)

  def OnChange(self, evt):
    self.Rescan()
    super().OnChange(evt)

  def Rescan(self):
    #BUGPRINT('CatalystsPanel.Rescan()')
    self.catalystThings = []
    pp = self.world.player.pos
    for q in self.world.IterRectAround(self.world.player.pos, 1):
      (numthings, something) = self.world.ThingsAt(q)
      if numthings and something and something.IsWorkstation():
        self.catalystThings.append(something)

  def OnRender(self, surf):
    i = 0
    for catalystThing in self.catalystThings:
      icon = catalystThing.GetIcon((self.size, self.size))
      surf.blit(icon, (i*self.size, 0))
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

class ProductsPanel(Window):
  def __init__(self, parent, **kwargs):
    super().__init__(parent, **kwargs)
    self.size = 64
    self._consumables = []
    self._productSomeThings = []
  def SetProducts(self, consumables, somethings):
    self._consumables = consumables
    self._productSomeThings = somethings
    #BUGPRINT("productSomeThings = {}", somethings)
    self.Dirty()
  def GetProducts(self):
    return self._productSomeThings[:]
  def OnRender(self, surf):
    BUGPRINT('ProductsPanel.OnRender()')
    super().OnRender(surf)
    i = 0
    for numthing, productThing in self._productSomeThings:
      BUGPRINT('Rendering product #{}', i)
      icon = productThing.GetIcon((self.size, self.size))
      surf.blit(icon, (i*self.size, 0))
      i += 1

# Crafting Productions:
# [ catalyst_list, pattern_matrix, output_constructor ]
# m is the matrix of input Thing instances that matched the pattern

barehand_productions = \
  [ ([], [[Stone],[Stone]],         lambda m: [(1,AxeHead(Stone()))])
  , ([], [[Stone],[Wood]],          lambda m: [(1,Hammer(m[0][0]))])
  , ([], [[AxeHead],[Wood]],        lambda m: [(1,Woodaxe(m[0][0].Material()))])
  , ([], [[PickaxeHead],[Wood]],    lambda m: [(1,Pickaxe(m[0][0].Material()))])
  , ([], [[Wood,Wood],[Wood,Wood]], lambda m: [(1,CampFire())])
  , ([], [[Stone,Stone],[Stone,Stone],[Charcoal,Charcoal]], lambda m: [(1,StoneFurnace())])
  , ([], [[Brick,Brick],[Brick,Brick],[Charcoal,Charcoal]], lambda m: [(1,BrickFurnace())])
  , ([], [[FireBrick,FireBrick],[FireBrick,FireBrick],[Charcoal,Charcoal]], lambda m: [(1,FireBrickFurnace())])
  ]

campfire_productions = \
  [ ([CampFire], [[Wood]],           lambda m: [(1,Charcoal())])
  # For now, smelt ores that melt up to 1373K
  , ([CampFire], [[Bismuthinite]],   lambda m: [(2,Bismuth())])
  , ([CampFire], [[Malachite]],      lambda m: [(2,Copper())])
  , ([CampFire], [[NativeGold]],     lambda m: [(2,Gold())])
  , ([CampFire], [[NativeSilver]],   lambda m: [(2,Silver())])
  , ([CampFire], [[Tetrahedrite]],   lambda m: [(2,Copper()),(1,Silver())])
  , ([CampFire], [[Copper,Tin]],     lambda m: [(2,Bronze())])
  , ([CampFire], [[Silver,Gold]],    lambda m: [(2,Electrum())])
  , ([CampFire], [[Metal],[Metal]],  lambda m: ( [], [(1,PickaxeHead(m[0][0]))] )[ m[0][0] == m[1][0] ])
  ]

stonefurnace_productions = [ ([StoneFurnace], pattern, fn) for (_,pattern,fn) in campfire_productions ] + \
  [ ([StoneFurnace], [[Clay],[Grass]], lambda m: [(1,Brick())])
  , ([StoneFurnace], [[Galena]],       lambda m: [(2,Lead()),(1,Silver())])
  ]

brickfurnace_productions = [ ([BrickFurnace], pattern, fn) for (_,pattern,fn) in stonefurnace_productions ] + \
  [ ([BrickFurnace], [[NativeAluminum],[Clay],[Clay],[Clay]], lambda m: [(4, FireBrick())])
  , ([BrickFurnace], [[Hematite]],       lambda m: [(2,Iron())])
  , ([BrickFurnace], [[Limonite]],       lambda m: [(2,Iron())])
  , ([BrickFurnace], [[Magnetite]],      lambda m: [(2,Iron())])
  , ([BrickFurnace], [[NativePlatinum]], lambda m: [(2,Platinum())])
  ]

firebrickfurnace_productions = [ ([FireBrickFurnace], pattern, fn) for (_,pattern,fn) in brickfurnace_productions ] + \
  [ ([FireBrickFurnace], [[Cassiterite]],    lambda m: [(2,Tin())])
  , ([FireBrickFurnace], [[Garnierite]],     lambda m: [(2,Nickel())])
  , ([FireBrickFurnace], [[NativeAluminum]], lambda m: [(2,Aluminum())])
  , ([FireBrickFurnace], [[Sphalerite]],     lambda m: [(2,Zinc())])
  ]

crafting_productions = barehand_productions + campfire_productions + stonefurnace_productions + brickfurnace_productions + firebrickfurnace_productions

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
    self.catalystsWnd = CatalystsPanel(self, world)
    self.matrixWnd = MatrixPanel(self, text='matrix panel')
    #self.outputSlot = ProductSlot(self, text='output')
    self.buildButton = Button(self, text='<--')
    self.productsWnd = ProductsPanel(self)
    self.catalystsWnd.Subscribe(CHANGE, self.OnMatrixChanged)
    self.matrixWnd.Subscribe(CHANGE, self.OnMatrixChanged)
    self.buildButton.Subscribe(CLICK, self.OnClick)
    self.world.player.Subscribe(CHANGE, self.OnPlayerChanged)
    self.matrix = [[]]
    self.consumables = []

  def OnResize(self, oldSize):
    r = self.localRect.inflate(-8,-8)
    self.inventWnd.Resize(pygame.Rect(r.left, r.top, r.width//3, r.height))
    self.catalystsWnd.Resize(pygame.Rect(self.inventWnd.rect.right, r.top, r.width//3, 64))
    self.matrixWnd.Resize(pygame.Rect(self.inventWnd.rect.right, self.catalystsWnd.rect.bottom+8, r.width//3, r.height//2))
    #self.outputSlot.Resize(pygame.Rect(self.matrixWnd.rect.centerx-32, self.matrixWnd.rect.bottom, 64,64))
    self.buildButton.Resize(pygame.Rect(self.matrixWnd.rect.left, self.matrixWnd.rect.bottom, 64, 64))
    self.productsWnd.Resize(pygame.Rect(self.matrixWnd.rect.left+64, self.matrixWnd.rect.bottom, self.matrixWnd.rect.width-64,64))

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
    BUGPRINT("CraftingWnd.OnChange() !")

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
    catalystTypesPresent = tuple( type(catalystThing) for catalystThing in self.catalystsWnd.catalystThings )
    for (catalystTypes, pattern, fresults) in crafting_productions:
      #print('comparing',pattern)
      found = False
      if not all(catalystType in catalystTypesPresent for catalystType in catalystTypes):
        continue
      if len(pattern) != len(self.matrix) or len(pattern[0]) != len(self.matrix[0]):
        continue
      found = True
      for (row, col) in ((r,c) for r in range(len(pattern)) for c in range(len(pattern[r]))):
        if not isinstance(self.matrix[row][col], pattern[row][col]):
          found = False
          break
      if found:
        break
    if found:
      #print('Pattern match: {} -> {}'.format(pattern,result))
      #self.outputSlot.SetProduct(self.consumables, fresult(self.matrix))
      resultList = fresults(self.matrix)
      if resultList:
        self.productsWnd.SetProducts(self.consumables, resultList)
        self.UpdateOutputEnabled()
      else:
        found = False
    if not found:
      #self.outputSlot.SetProduct(None, None)
      self.productsWnd.SetProducts([], [])

  def UpdateOutputEnabled(self):
    #self.outputSlot.SetEnabled( self.world.player.HasThings( (1, t) for t in self.consumables ) )
    self.productsWnd.SetEnabled( self.world.player.HasThings( (1, t) for t in self.consumables ) )

  def OnClick(self, evt):
    BUGPRINT('CraftingWnd.OnClick({})', evt)
    if self.world.player.HasThings( (1, t) for t in self.consumables ):
      for t in self.consumables:
        numremoved, thingremoved = self.world.player.RemoveInventory( (1, t) )
      for p in self.productsWnd.GetProducts():
        self.world.player.AddInventory( p )

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
    BUGPRINT('DummyClick!')

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
  BUGPRINT('{}', ' '.join(fields))

def ChooseVideoMode(margin=(96,96)):
  modes = pygame.display.list_modes()
  if modes is -1:
    return (0,0)
  vi = pygame.display.Info()
  if vi.current_h > margin[1] and vi.current_w > margin[0]:
    target = (vi.current_w - margin[0], vi.current_h - margin[1])
    for m in modes:
      if m[0] <= target[0] and m[1] <= target[1]:
        BUGPRINT('Display resolution: {}', m)
        return m
  return (0,0)

class Application:

  def __init__(self, argv):
    self.ParseArgs(argv)
    self.InitApp()

  def ParseArgs(self, argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--debug', action='store_true', help='Turn on debugging output')
    ap.add_argument('--dm', action='store_true', help='Play as Dungeon Master')
    ap.add_argument('--overclock', type=int, default=1, help='Run the simulation at N times speed')
    self.opts = ap.parse_args(argv[1:])
    if self.opts.debug:
      global _DEBUG
      _DEBUG = True

  def InitApp(self):
    print("Initializing...")
    pygame.init()
    pygame.mixer.quit()  # stop pygame 100% CPU bug circa 2017-2018
    global manager
    manager = WindowManager(text='manager')

    #screen = pygame.display.set_mode((1536,800))
    self.screen = pygame.display.set_mode(ChooseVideoMode(), pygame.RESIZABLE)

    screct = self.screen.get_rect()
    barect = pygame.Rect(screct.width//4, screct.centery-16, screct.width//2, 32)
    progressBar = ProgressBar(manager, barect, 0, text='Initializing...')
    def UpdateProgress(p):
      progressBar.SetProgress(p)
      pygame.display.update(manager.RenderDirtyNow(self.screen))
    UpdateProgress(0)

    if _DEBUG:
      if self.screen.get_flags() & pygame.HWACCEL: print("screen is HARDWARE ACCELERATED!")
      if self.screen.get_flags() & pygame.HWSURFACE: print("screen is in video memory")
    pygame.display.set_caption("SquareWorldCraft")
    icon = pygame.image.load('icons/nested-squares-icon.png')
    pygame.display.set_icon(icon)
    #pygame.key.set_repeat(100, 100)

    LoadMaterialsProperties()
    UpdateProgress(5)
    self.world = World()
    self.world.Generate(UpdateProgress)
    self.world.MovePlayerToEmptySpot()
    self.appWnd = AppWnd(manager, self.screen, self.world, text='appWnd')

    #monofont = pygame.font.SysFont('freemono',16,bold=True)
    #font_test_img = monofont.render('MWQj|_{}[]', False, (0,0,0))
    #print('freemono 16 is {} px high'.format(font_test_img.get_height()))
    #assert font_test_img.get_height() == 17

    if self.opts.dm:
      self.world.player.AddInventory( (1, Woodaxe(Stone())) )
      self.world.player.AddInventory( (1, Pickaxe(Iron())) )
      self.world.player.AddInventory( (3, CampFire()) )
      self.world.player.AddInventory( (1, Pickaxe(Diamond())) )
      self.world.player.walkingSpeed = SECOND//30

    print("Ready.")
    UpdateProgress(100)
    progressBar.Delete()

  def MainLoop(self):
    clock = pygame.time.Clock()
    if self.opts.overclock > 1:
      target_fps = 12
    else:
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
          self.screen = pygame.display.set_mode(evt.size, pygame.RESIZABLE)
          manager.Resize(pygame.Rect((0,0),evt.size))
          self.appWnd.Resize(pygame.Rect((0,0),evt.size))
        else:
          manager.OnEvent(evt)
      # Update state
      self.world.Update(dt*self.opts.overclock)
      #if self.world.changed:
      #  print('world changed')
      #  self.appWnd.Dirty()
      # Update screen
      dirtyList = manager.RenderDirtyNow(self.screen)
      if dirtyList:
        label_text = '{:4d}x{:<4d}, {:4d} ms, {:3d} fps'.format(self.screen.get_width(), self.screen.get_height(), dt, SECOND//elapsed)
        fps_label = manager.GetFont('LABEL').render(label_text, False, (255,255,0))
        self.screen.blit(fps_label, ( self.screen.get_width() - fps_label.get_width()
                                    , self.screen.get_height() - fps_label.get_height()
                                    ))
        self.world.player.Changed(False)
        self.world.Changed(False)
        pygame.display.update(dirtyList)
      assert not (self.world.changed or self.world.player.changed)
      elapsed = clock.tick(target_fps)
      # On next timeslice, compensate for actual elapsed time.
      dt = elapsed  # dt_std + (dt_std - elapsed)
      #print('elapsed = {} ms, dt = {} ms'.format(elapsed,dt))
    return 0


def main(argv):
  if '--profile' in argv:
    sys.argv.remove('--profile')
    import cProfile
    return cProfile.run('main(sys.argv)', sort='cumulative')
  app = Application(argv)
  rc = 3
  try:
    rc = app.MainLoop()
  finally:
    pygame.quit()
  return rc

if __name__=='__main__': sys.exit(main(sys.argv))

