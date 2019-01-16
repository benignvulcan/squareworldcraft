#!/usr/bin/env python3
# Copyright © 2018 Marty White under the GNU GPLv3+
'A simple pygame windowing library'

'''
TODO: 
  * actually use dirty rect list in OnRedraw
'''

import pygame, enum, math, colorsys

_DEBUG = False

def Dist(p, q):
  return math.hypot(q[0]-p[0], q[1]-p[1])

def RectToPoly(r, closed=False):
  'Return an open polygon corresponding to the given rectangle, for purposes of pygame.draw'
  # The right/bottom edges of a rectangle effectively lie outside the area drawn by pygame.draw.rect(),
  # while all edges of a polygon are treated the same by pygame.draw.polygon().
  p = [ (r.left,r.top), (r.right-1,r.top), (r.right-1,r.bottom-1), (r.left,r.bottom-1) ]
  if closed:
    p.append(p[0])
  return p

def RectInsetFramePolys(aRect, thickness):
  'Return a pair of polygons suitable for painting the (left+top, right+bottom) parts of an inset frame'
  outer = pygame.Rect(aRect)
  outer.width  -= 1
  outer.height -= 1
  return ( [ outer.bottomleft, outer.topleft, outer.topright
           , (outer.right, outer.top+thickness-1), (outer.left+thickness-1,outer.top+thickness-1), (outer.left+thickness-1, outer.bottom) ]
         , [ outer.topright, outer.bottomright, outer.bottomleft
           , (outer.left, outer.bottom-thickness+1), (outer.right-thickness+1, outer.bottom-thickness+1), (outer.right-thickness+1, outer.top) ]
         )

#print(RectInsetFramePolys(pygame.Rect(0,0,8,8),1))
#print(RectInsetFramePolys(pygame.Rect(0,0,8,8),2))

def draw_polygon_filled(surf, color, points):
  pygame.draw.polygon(surf, color, points, 1)
  pygame.draw.polygon(surf, color, points, 0)

def BitSeqToInt(bits):
  value = 0
  i = 0
  for b in (bits):
    value |= b << i
    i += 1
  return value

def HSV2RGB(hsv):  # h=0-360, s=0-100, v=0-100
  h, s, v = hsv
  rgb = colorsys.hsv_to_rgb(h/360,s/100,v/100)
  return (int(rgb[0]*255),int(rgb[1]*255),int(rgb[2]*255))

assert HSV2RGB((0,0,0)) == (0,0,0)
assert HSV2RGB((0,0,50)) == (127,127,127)
assert HSV2RGB((0,0,100)) == (255,255,255)

_UE0 = pygame.USEREVENT
CHANGE  = _UE0 + 1
CLICK   = _UE0 + 2
DROP    = _UE0 + 3

class Observable:
  'An object that can notify subscribers of events'
  def __init__(self, *posargs, **kwargs):
    super().__init__(*posargs, **kwargs)
    self.subscriptions = {}     # Map from pygame.Event.type to set of callback functions
  def Subscribe(self, eventType, callback):
    self.subscriptions.setdefault(eventType, set()).add(callback)
  def Unsubscribe(self, eventType, callback):
    self.subscriptions[eventType].remove(callback)
  def NotifyEvent(self, event):
    for callback in self.subscriptions.get(event.type, set()):
      callback(event)
  def NotifyEventType(self, eventType, **kwargs):
    self.NotifyEvent(pygame.event.Event(eventType, sender=self, **kwargs))
  def NotifyChange(self, **kwargs):
    self.NotifyEventType(CHANGE, **kwargs)
  def OnChange(self, evt):
    self.NotifyEvent(evt)  # default is to cascade to this Observable's subscribers
    return True

class Window(Observable):
  'An input/output region of the screen'

  '''
  In this implementation:
    * Window is responsible for:
      - returning False if it doesn't handle a message
      - drawing its own border, if any
      - calculating its own client space, if needed
  '''

  mouseCaptureWnd = None # Ensure same window gets all mouse events from first button down to last button up
  mouseCaptureButtons = 0
  #keyCaptureWnd = None  # Ensure same window gets all key events from first key down to last key up
  #keyCaptureKeys = set()

  def __init__(self, parentWnd, rect=None, isModal=False, text=None, **kwargs):
    super().__init__(**kwargs)
    self.parentWnd = parentWnd  # Direct parent of this window.
    self.isModal = isModal
    self.text = text            # Textual content of Window
    self.childWndList = []      # List of direct children of this window.

    if rect is None:
      rect = pygame.Rect(0,0,0,0)
    # Position of this window relative to its parent, and its size.
    # The WindowManager will use this to help decide which inputs you get.
    # Use Resize() to change.
    self.rect = rect
    self.localRect = pygame.Rect(0,0,rect.width,rect.height)

    self.dirtyRects = []        # IN PARENT COORDINATES; When not empty, OnRender will be called at next convenient time
    self.visible = True
    self.enabled = True
    self.isActive = False       # This is for your benefit.  The WindowManager doesn't care.

    if not self.parentWnd is None:
      self.parentWnd.AddChildWnd(self)

  def Delete(self):
    'Disconnect this Window from its parent'
    if not self.parentWnd is None:
      self.parentWnd.Dirty(self.rect)
      self.parentWnd.RemoveChildWnd(self)
    self.deleted = True

  def GetGreatestParent(self):
    if self.parentWnd is None:
      return self
    return self.parentWnd.GetGreatestParent()

  def AddChildWnd(self, wnd):
    if wnd.parentWnd is None:
      wnd.parentWnd = self
    self.childWndList.insert(0, wnd)
    self.Dirty()
    return wnd

  def RemoveChildWnd(self, wnd):
    self.childWndList = [w for w in self.childWndList if not w is wnd]
    wnd.parentWnd = None
    return wnd

  def RaiseChildWnd(self, wnd):
    assert wnd in self.childWndList
    wasActive = (self.childWndList[:1] == [wnd])
    self.childWndList = [wnd] + [w for w in self.childWndList if not w is wnd]
    if wasActive: wnd.OnActivationChange(True)
    return wnd

  def Raise(self):
    return self.parentWnd.RaiseChildWnd(self)

  def GetColorTheme(self):
    if hasattr(self, 'colorTheme'):
      return self.colorTheme
    elif self.parentWnd is None:
      return None
    else:
      return self.parentWnd.GetColorTheme()

  def SetColorTheme(self, colorTheme):
    self.colorTheme = colorTheme

  def GetFont(self, font_purpose):
    if self.parentWnd is None:
      return None
    else:
      return self.parentWnd.GetFont(font_purpose)

  def OnActivationChange(self, newState):
    self.isActive = newState

  def SetVisible(self, isVisible):
    if isVisible and not self.visible:
      self.Dirty()
    elif not self.parentWnd is None and not isVisible and self.visible:
      self.parentWnd.Dirty()
    self.visible = isVisible

  def SetEnabled(self, isEnabled):
    if isEnabled != self.enabled:
      self.enabled = isEnabled
      self.Dirty()

  def Resize(self, newRect):
    'Resize (and reposition) this window and send self an OnResize message'
    #print('Window.Resize({})'.format(newRect))
    oldRect = self.rect
    self.rect = pygame.Rect(newRect)
    self.localRect = pygame.Rect(0,0,newRect.width,newRect.height)
    self.Dirty()  # TODO: only dirty enlarged portions
    self.OnResize(oldRect)

  def OnResize(self, oldRect):
    'Override this to change the size & position of child windows when resized.'
    #print('Window.OnResize({})'.format(oldRect))
    #self.Dirty()

  def MapPointFromParent(self, point):
    "Given a point in parentWnd's coordinate system, return it in this Window's coordinate system"
    return (point[0] - self.rect.left, point[1] - self.rect.top)

  def MapPointToParent(self, point):
    return (self.rect.left + point[0], self.rect.top + point[1])

  def MapPointFromGlobal(self, point):
    "Given a point in the top-most parent's coordinate system, return it in this Window's coordinate system"
    if not self.parentWnd is None:
      point = self.parentWnd.MapPointFromGlobal(point)
    return self.MapPointFromParent(point)

  def MapPointToGlobal(self, point):
    point = self.MapPointToParent(point)
    if not self.parentWnd is None:
      point = self.parentWnd.MapPointToGlobal(point)
    return point

  def MapEventFromParent(self, evt):
    if hasattr(evt, 'pos'):
      d = dict(evt.__dict__)
      d['pos'] = self.MapPointFromParent(evt.pos)
      evt = pygame.event.Event(evt.type, d)
    return evt

  def MapEventFromGlobal(self, evt):
    if hasattr(evt, 'pos'):
      d = dict(evt.__dict__)
      d['pos'] = self.MapPointFromGlobal(evt.pos)
      evt = pygame.event.Event(evt.type, d)
    return evt

  def OnKeyDown(self, evt):
    return False

  def OnKeyUp(self, evt):
    return False

  def OnMouseMove(self, evt):
    return False

  def OnMouseButtonDown(self, evt):
    return False

  def OnMouseButtonUp(self, evt):
    return False

  def OnChange(self, evt):
    self.Dirty()
    return super().OnChange(evt)

  def OnClick(self, evt):
    return False

  def OnDrop(self, evt):
    return False

  def DispatchEvent(self, evt):
    # Assumes evt is in LOCAL coordinate system.
    #if self.DispatchEvent(evt)             : return True
    if   evt.type is pygame.MOUSEMOTION    : return self.OnMouseMove(evt)
    elif evt.type is pygame.MOUSEBUTTONDOWN: return self.OnMouseButtonDown(evt)
    elif evt.type is pygame.MOUSEBUTTONUP  : return self.OnMouseButtonUp(evt)
    elif evt.type is pygame.KEYDOWN        : return self.OnKeyDown(evt)
    elif evt.type is pygame.KEYUP          : return self.OnKeyUp(evt)
    elif evt.type is CHANGE                : return self.OnChange(evt)
    elif evt.type is CLICK                 : return self.OnClick(evt)
    elif evt.type is DROP                  : return self.OnDrop(evt)
    else                                   : return False

  def DispatchCapturedKeyboard_UNUSED(self, evt):
    # Pass keyboard events to same window until all keyboard keys are up.
    self.keyCaptureWnd.DispatchEvent(evt)
    if evt.type is pygame.KEYDOWN:
      self.keyCaptureKeys.add(evt.key)
    elif evt.type is pygame.KEYUP:
      if not evt.key in self.keyCaptureKeys: print("keyCaptureKeys:", self.keyCaptureKeys)
      #self.keyCaptureKeys.remove(evt.key)
      self.keyCaptureKeys = set( k for k in self.keyCaptureKeys if not k is evt.key )
      if not self.keyCaptureKeys:
        self.keyCaptureWnd = None
    return True

  def CaptureMouse(self, buttonBits):
    Window.mouseCaptureWnd = self
    assert Window.mouseCaptureButtons == 0
    Window.mouseCaptureButtons = buttonBits

  def ReleaseMouse(self):
    assert Window.mouseCaptureWnd is self
    Window.mouseCaptureWnd = None
    Window.mouseCaptureButtons = 0

  def DispatchCapturedMouse(self, evt):
    'Pass mouse events to the mouse capture window until all mouse buttons are up.'
    # Assumes evt is in GLOBAL coordinate system.
    Window.mouseCaptureWnd.DispatchEvent(Window.mouseCaptureWnd.MapEventFromGlobal(evt))
    if evt.type is pygame.MOUSEBUTTONDOWN:
      Window.mouseCaptureButtons |= (1 << (evt.button-1))
    elif evt.type is pygame.MOUSEBUTTONUP:
      Window.mouseCaptureButtons &= ~(1 << (evt.button-1))
      if Window.mouseCaptureButtons == 0:
        Window.mouseCaptureWnd.ReleaseMouse()
    return True

  def OnEvent(self, evt):
    'Send event to descendant (deepest first) windows or this one until accepted.'
    # Assumes evt is in GLOBAL coordinate system.
    #if hasattr(evt, 'pos'): print('Window {} OnEvent: pos = {}'.format(id(self), evt.pos))
    # While button(s) are down, continue to send relevant events to the same window.
    # Otherwise, pass event to every window in the list until one "accepts" it.
    if (not Window.mouseCaptureWnd is None) and (evt.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP, pygame.MOUSEBUTTONDOWN)):
      return self.DispatchCapturedMouse(evt)
    #elif not self.keyCaptureWnd is None and evt.type in (pygame.KEYDOWN, pygame.KEYUP):
    #  return self.DispatchCapturedKeyboard(evt)
    # Send to children first.
    for wnd in self.childWndList:
      if wnd.visible and wnd.OnEvent(evt):
        return True
    # If not handled by children, see if this Window is interested.
    if not hasattr(evt, 'pos') or self.localRect.collidepoint(self.MapPointFromGlobal(evt.pos)):
      if self.DispatchEvent(self.MapEventFromGlobal(evt)):
        if evt.type is pygame.MOUSEBUTTONDOWN and evt.button in (1,2,3):
          # A button-down event was accepted by this window,
          # so capture future related events until all buttons are up.
          self.CaptureMouse(1 << (evt.button-1))
        #elif evt.type is pygame.KEYDOWN:
        #  self.keyCaptureWnd = wnd
        #  self.keyCaptureKeys.add(evt.key)
        return True
    # Modal windows swallow all events to prevent other windows from getting them.
    # Non-modal windows report non-acceptance.
    return self.isModal

  def Dirty(self, rect=None):
    'Mark an area of the window as needing re-rendering.'
    if rect is None:
      rect = pygame.Rect(self.rect)
    if not rect in self.dirtyRects:
      self.dirtyRects.append(rect)
      if len(self.dirtyRects) > 7: print('warning: {} dirtyRects'.format(len(self.dirtyRects)))

  def RenderFill(self, surf):
    # Default is to render a white background with a black border.
    surf.fill( self.GetColorTheme()['bg'] )

  def RenderFrame(self, surf):
    #pygame.draw.rect(surf, (0,0,0), pygame.Rect(0,0,self.localRect.width-2,self.localRect.height-2), 2)
    pygame.draw.rect(surf, self.GetColorTheme()['fg'], self.localRect, 2)

  def RenderImage(self, surf):
    if hasattr(self, 'image') and self.image:
      # TODO: automatically rescale and center?
      surf.blit(self.image, (0,0))

  def RenderText(self, surf):
    if self.text:
      textimg = self.GetFont('TEXT').render(self.text, True, self.GetColorTheme()['fg'])
      return surf.blit(textimg, (surf.get_width()/2 - textimg.get_width()/2, surf.get_height()/2 - textimg.get_height()/2))

  def OnRender(self, surf):
    'Repaint contents of this window.  Called before repainting any children.'
    # self.dirtyRects contains list of rectangles needing repainting.
    #print('Window.OnRender({}), self.rect=={}'.format(surf.get_rect(),self.rect))
    self.RenderFill(surf)
    self.RenderFrame(surf)
    if hasattr(self, 'image') and self.image:
      self.RenderImage(surf)
    else:
      self.RenderText(surf)
    #pygame.display.flip()
    #import time
    #time.sleep(.05)
    return [surf.get_rect()]

  def RenderDirtyNow(self, surf, _force=False, _indent='  '):
    'If any Windows are dirty, re-render them.'
    #print('Window.RenderDirtyNow({}), self.rect=={}'.format(surf.get_rect(),self.rect))
    if _force or self.dirtyRects:
      dirtyList = self.OnRender(surf)   # render parent (background) window first
      if dirtyList is None:
        dirtyList = [surf.get_rect()]
      #_force = True
    else:
      dirtyList = []
    #if self.childWndList: print(_indent+'{} child windows:'.format(len(self.childWndList)))
    for child in reversed(self.childWndList):  # render in back-to-front order
      if not child.visible:
        continue
      # TODO:
      #   child window has no way of knowing the surface has been clipped,
      #     so either tell it or provide it a temporary (full child-sized) surface to render to.
      clipped_child = child.rect.clip(surf.get_rect())
      #print(_indent+'{}.clip({}) -> {}'.format(child.rect, surf.get_rect(), clipped_child))
      if clipped_child.width < 1 or clipped_child.height < 1:
        continue
      if child.rect.collidelist(dirtyList) != -1:
        # If repainted this window or overlapping sibling, then child is dirty.
        child.Dirty()
      ss = surf.subsurface(clipped_child)
      childDirtyList = child.RenderDirtyNow(ss, _force=_force, _indent='  '+_indent)
      #print(_indent+'child.RenderDirtyNow({}) -> {}'.format(ss.get_rect(), childDirtyList))
      assert child.dirtyRects == []
      for r in childDirtyList:
        dirtyList.append(r.move(child.rect.left,child.rect.top))
    #print(_indent+self.text, dirtyList)
    self.dirtyRects = []
    return dirtyList

class ColorTheme:
  '''A proper color scheme is an enormously problematic issue.
    Simple outputs include colors for:
      foreground/figure (incl. font color)
      background/ground
      highlight
      lowlight
      hover (or not) (inapplicable to contact-touch devices)
      focused (or not)
      depressed (or not)
      selected (or not)
    tint = mix with white
    tone = mix with gray
    shade = mix with black
  '''
  def __init__(self, colorTheme=None, hue=None, saturation=None):
    self._values = \
      { 'bg' : 75
      , 'fg' : 0
      , 'hi' : 100
      , 'lo' : 0
      , 'bg_selected' : 88
      , 'fg_selected' : 0
      }
    self._hue = 0
    self._sat = 0
    if not colorTheme is None:
      self._values.update(colorTheme._values)
      self._hue = colorTheme._hue
      self._sat = colorTheme._sat
    if not hue is None:
      self._hue = hue
    if not saturation is None:
      self._sat = saturation

  def __getitem__(self, key):
    return HSV2RGB((self._hue, self._sat, self._values.get(key)))

  def SetValue(self, key, value):
    assert key in self._values
    self._values[key] = value
    return self

  def Colored(self, hue, saturation):
    'Return a new ColorTheme with the given hue and saturation'
    return ColorTheme(colorTheme=self, hue=hue, saturation=saturation)

  def InvertedValue(self):
    ct = ColorTheme(self)
    for key in ct._values:
      ct._values[key] = 100 - ct._values[key]
    return ct

class WindowManager(Window):

  'A special Window that acts as a top-most container of Windows.'

  def __init__(self, **kwargs):
    assert not 'parentWnd' in kwargs
    super().__init__(None, **kwargs)
    self.colorTheme = ColorTheme()
    self.fonts = {}
    self.SetFonts()

  def SetFonts(self, fontName='freemono', labelSize=12, textSize=14):
    self.fonts['LABEL'] = pygame.font.SysFont(fontName, labelSize, bold=True)
    self.fonts['TEXT' ] = pygame.font.SysFont(fontName, textSize , bold=True)

  def GetFont(self, font_purpose):
    return self.fonts[font_purpose]

  def AddChildWnd(self, wnd):
    super().AddChildWnd(wnd)
    wnd.OnActivationChange(True)
    return wnd

  def RemoveChildWnd(self, wnd):
    if self.childWndList[:1] == [wnd]:
      wnd.OnActivationChange(False)
    super().RemoveChildWnd(wnd)
    return wnd

class ProgressBar(Window):

  def __init__(self, parentWnd, rect=None, progress=0, **kwargs):
    super().__init__(parentWnd, rect=rect, **kwargs)
    self.progress = progress
    self.colorTheme = parentWnd.GetColorTheme().Colored(120,100).InvertedValue().SetValue('bg',0)

  def SetProgress(self, newProgress):
    self.progress = newProgress
    self.Dirty()

  def OnRender(self, surf):
    self.RenderFill(surf)
    self.RenderFrame(surf)
    colors = self.GetColorTheme()
    #pygame.draw.rect(surf, colors['bg'], self.localRect)
    BORDER = 2
    pbar = pygame.Rect(self.localRect).inflate(-BORDER, -BORDER)
    pbar.width = pbar.width * self.progress // 100
    if _DEBUG: print('pbar =',pbar)
    pygame.draw.rect(surf, colors['fg'], pbar)

class Button(Window):

  def __init__(self, parentWnd, *posargs, **kwargs):
    super().__init__(parentWnd, *posargs, **kwargs)
    self.isDepressed = False
    self.isSelected = False

  def Selected(self, value=None):
    if value is None:
      return self.isSelected
    elif value != self.isSelected:
      self.isSelected = value
      self.Dirty()

  def SetDepressed(self, value):
    if value != self.isDepressed:
      self.isDepressed = value
      self.Dirty()

  def OnMouseButtonDown(self, evt):
    #print('Button.OnMouseButtonDown: pos = {}, button = {}'.format(evt.pos, evt.button))
    if evt.button == 1:
      self.SetDepressed(True)
      return True
    return False

  def OnMouseMove(self, evt):
    #print('Button.OnMouseMove: pos = {}, id = {}'.format(evt.pos, self.id))
    if 1 in evt.buttons:
      self.SetDepressed(self.localRect.collidepoint(evt.pos))

  def OnMouseButtonUp(self, evt):
    #print('Button.OnMouseButtonUp: pos = {}, button = {}'.format(evt.pos, evt.button))
    self.SetDepressed(False)
    if evt.button == 1 and self.localRect.collidepoint(evt.pos):
      #self.isSelected = not self.isSelected
      self.NotifyEventType(CLICK)
    return True

  def OnRender(self, surf):
    colors = self.GetColorTheme()
    if self.isSelected:
      bg = colors['bg_selected']
    else:
      bg = colors['bg']
    if self.isDepressed:
      e1 = colors['hi']
      e2 = colors['lo']
    else:
      e1 = colors['lo']
      e2 = colors['hi']
    pygame.draw.rect(surf, bg, self.localRect)
    thickness = 2
    tl, br = RectInsetFramePolys(self.localRect, thickness)
    draw_polygon_filled(surf, e1, br)
    draw_polygon_filled(surf, e2, tl)
    if hasattr(self, 'image') and self.image:
      interior = self.localRect.inflate(-thickness*2, -thickness*2)
      surf.blit(self.image, (thickness,thickness), area=interior)
    else:
      self.RenderText(surf)

class DraggingWnd(Window):
  'A Window that keeps moving itself to remain under the mouse until button-up'

  def __init__(self, parentWnd, rect, clickPos, sender, data, *posargs, **kwargs):
    #print('DragginWnd.__init__( , clickPos={})'.format(clickPos))
    super().__init__(parentWnd, rect, *posargs, **kwargs)
    self.firstPos = clickPos
    self.lastPos = clickPos
    self.sender = sender
    self.data = data

  def OnMouseMove(self, evt):
    #print('DragginWnd.OnMouseMove(pos={})'.format(evt.pos))
    dx = evt.pos[0] - self.lastPos[0]
    dy = evt.pos[1] - self.lastPos[1]
    self.rect.move_ip(dx,dy)
    self.Dirty()
    self.parentWnd.Dirty()

  def OnMouseButtonUp(self, evt):
    #print('DragginWnd.OnMouseButtonUp()')
    if evt.button == 1:
      pos = self.MapPointToGlobal(evt.pos)
      #self.GetGreatestParent().OnEvent(Drop(self.sender))
      pygame.event.post(pygame.event.Event(DROP, pos=pos, sender=self.sender, data=self.data))
      # TODO: instead of immediately deleting, wait for accept/reject, and upon rejection animate back to firstPos
      self.Delete()

  #def OnRender(self, surf):
  #  dirty = super().OnRender(surf)
  #  surf.fill( (127,127,0,127) )
  #  return dirty

class DraggableHolder(Window):
  'A Window containing something that could be dragged to another Window'

  def __init__(self, parentWnd, *posargs, data=None, **kwargs):
    super().__init__(parentWnd, *posargs, **kwargs)
    self.dragOrigin = None
    self.dragWnd = None
    self.data = data

  def OnMouseButtonDown(self, evt):
    if evt.button == 1 and self.dragOrigin is None:
      self.dragOrigin = evt.pos

  def OnMouseMove(self, evt):
    if not self.dragOrigin is None:
      if Dist(self.dragOrigin, evt.pos) > 2:
        self.BeginDragging(evt)

  def OnMouseButtonUp(self, evt):
    self.dragOrigin = None

  def BeginDragging(self, evt):
    if not self.enabled: return
    p = self.MapPointToGlobal((0,0))
    #print('DraggableHolder.BeginDragging(pos={}), global p = {}'.format(evt.pos, p))
    if _DEBUG and self.text:
      text = 'DRG'+str(self.text)
    else:
      text = None
    self.dragWnd = DraggingWnd(self.GetGreatestParent(), pygame.Rect(p, self.rect.size), self.dragOrigin, self, self.data, text=text)
    if hasattr(self, 'image'):
      self.dragWnd.image = self.image
    self.dragWnd.CaptureMouse(BitSeqToInt(evt.buttons))
    self.dragOrigin = None

  #def OnDrop(self, evt):
  #  print("OnDrop(pos={})".format(evt.pos))
  #  return True

  def OnRender(self, surf):
    self.RenderFill(surf)
    thickness = 2
    tl, br = RectInsetFramePolys(self.localRect, thickness)
    colors = self.GetColorTheme()
    draw_polygon_filled(surf, colors['hi'], br)
    draw_polygon_filled(surf, colors['lo'], tl)
    if hasattr(self, 'image') and self.image:
      interior = self.localRect.inflate(-thickness*2, -thickness*2)
      surf.blit(self.image, (thickness,thickness), area=interior)
    else:
      self.RenderText(surf)
    if not self.enabled:
      overlay = pygame.Surface(surf.get_size(), flags=pygame.SRCALPHA)
      overlay.fill( (127,127,127,127) )
      surf.blit(overlay, (0,0))

