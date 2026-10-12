# Business Logic: User Input Processing

## Description
Processes keyboard input to allow user interaction with the terminal-based interface.

## Logic Details
- **Escape Key (Esc)**: Triggers the exit condition, breaking the main application loop.
- **Enter Key (Enter/10/13)**: Validates the input text. If not empty, it initiates the creation of a new object and clears the current input buffer.
- **Backspace Key (Backspace/127/8)**: Removes the last character from the current input buffer.
- **Printable Characters (ASCII 32-126)**: Appends the corresponding character to the current input buffer.

## Input/Output
- **Inputs**: Keyboard events/scancodes from the `curses` library.
- **Outputs**: 
  - Modification of `input_text`.
  - Addition of new objects to the `objects` list.
  - Program termination signal.
