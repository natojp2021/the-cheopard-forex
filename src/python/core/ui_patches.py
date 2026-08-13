import tkinter
import sys
import customtkinter as ctk

# Preserve original methods of CTkButton
_orig_init = ctk.CTkButton.__init__
_orig_configure = ctk.CTkButton.configure
_orig_cget = ctk.CTkButton.cget

def patched_init(self, *args, **kwargs):
    # Extract disabled colors if provided in kwargs, otherwise use defaults
    # Sleek dark gray background and muted gray text
    d_fg = kwargs.pop("disabled_fg_color", "#2D2D2D")
    d_txt = kwargs.pop("disabled_text_color", "#5D665F")
    self._disabled_fg_color = d_fg
    self._disabled_text_color = d_txt

    # Determine the initial state
    state = kwargs.get("state", "normal")
    
    # Save the original fg_color and text_color if provided in kwargs
    self._saved_fg_color = kwargs.get("fg_color", None)
    self._saved_text_color = kwargs.get("text_color", None)
    
    if state == "disabled":
        if "fg_color" in kwargs:
            self._saved_fg_color = kwargs["fg_color"]
        kwargs["fg_color"] = self._disabled_fg_color
        
        if "text_color" in kwargs:
            self._saved_text_color = kwargs["text_color"]
        kwargs["text_color"] = self._disabled_text_color
        
    _orig_init(self, *args, **kwargs)
    
    # If colors were not in kwargs, retrieve them after init to save for future state toggles
    if self._saved_fg_color is None:
        try:
            self._saved_fg_color = self.cget("fg_color")
        except Exception:
            pass
    if self._saved_text_color is None:
        try:
            self._saved_text_color = self.cget("text_color")
        except Exception:
            pass

def patched_configure(self, require_redraw=False, **kwargs):
    # Pop disabled colors from configure kwargs if someone updates them
    if "disabled_fg_color" in kwargs:
        self._disabled_fg_color = kwargs.pop("disabled_fg_color")
    if "disabled_text_color" in kwargs:
        self._disabled_text_color = kwargs.pop("disabled_text_color")

    # Handle state changes dynamically
    if "state" in kwargs:
        state = kwargs["state"]
        if state == "disabled":
            # Save the current colors before disabling (only if they aren't the disabled colors already)
            try:
                curr_fg = self.cget("fg_color")
                curr_txt = self.cget("text_color")
                if curr_fg != self._disabled_fg_color:
                    self._saved_fg_color = curr_fg
                if curr_txt != self._disabled_text_color:
                    self._saved_text_color = curr_txt
            except Exception:
                pass
            
            kwargs["fg_color"] = self._disabled_fg_color
            kwargs["text_color"] = self._disabled_text_color
        else:
            # Restore saved colors
            if hasattr(self, "_saved_fg_color") and self._saved_fg_color is not None:
                kwargs["fg_color"] = self._saved_fg_color
            if hasattr(self, "_saved_text_color") and self._saved_text_color is not None:
                kwargs["text_color"] = self._saved_text_color
    else:
        # If state is not changed, but colors are updated in normal state, update our saved values
        current_state = getattr(self, "_state", "normal")
        if current_state != "disabled" and current_state != tkinter.DISABLED:
            if "fg_color" in kwargs:
                self._saved_fg_color = kwargs["fg_color"]
            if "text_color" in kwargs:
                self._saved_text_color = kwargs["text_color"]
                
    return _orig_configure(self, require_redraw=require_redraw, **kwargs)

def patched_cget(self, attribute_name: str) -> any:
    if attribute_name == "disabled_fg_color":
        return getattr(self, "_disabled_fg_color", "#2D2D2D")
    elif attribute_name == "disabled_text_color":
        return getattr(self, "_disabled_text_color", "#5D665F")
    return _orig_cget(self, attribute_name)

def patched_set_cursor(self):
    if self._cursor_manipulation_enabled:
        if self._state == tkinter.DISABLED or self._state == "disabled":
            cursor_name = "no" if sys.platform.startswith("win") else "arrow"
        else:
            # State is normal
            if getattr(self, "_command", None) is not None:
                cursor_name = "hand2" if sys.platform.startswith("win") else ("pointinghand" if sys.platform == "darwin" else "hand2")
            else:
                cursor_name = "arrow"
            
        try:
            tkinter.Frame.configure(self, cursor=cursor_name)
        except Exception:
            pass
            
        if hasattr(self, "_canvas") and self._canvas is not None:
            try:
                self._canvas.configure(cursor=cursor_name)
            except Exception:
                pass
        if hasattr(self, "_text_label") and self._text_label is not None:
            try:
                self._text_label.configure(cursor=cursor_name)
            except Exception:
                pass
        if hasattr(self, "_image_label") and self._image_label is not None:
            try:
                self._image_label.configure(cursor=cursor_name)
            except Exception:
                pass

# Apply monkeypatching to ctk.CTkButton
ctk.CTkButton.__init__ = patched_init
ctk.CTkButton.configure = patched_configure
ctk.CTkButton.cget = patched_cget
ctk.CTkButton._set_cursor = patched_set_cursor
