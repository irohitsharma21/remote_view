# Running the agent on Windows (host side)

You only need **two files** from this project on the Windows machine:

```
agent.py
requirements-agent.txt
```

Put them together in a folder, e.g. `C:\remote_control\`.

## 1. Install Python
Download Python 3.12 from <https://www.python.org/downloads/windows/>.
During install, **tick "Add python.exe to PATH"**.

## 2. Install dependencies (PowerShell or CMD, in that folder)
```powershell
cd C:\remote_control
python -m venv venv
venv\Scripts\activate
pip install -r requirements-agent.txt
```

## 3. Run the agent, pointing at the Mac
Replace `MAC_IP` with the Mac's address and use the same secret/code the Mac set.
```powershell
python agent.py --server ws://MAC_IP:8000 --secret mysecret --code 123456
```
- A red **"REMOTE SESSION ACTIVE"** banner appears with the agent id + access code.
- First run: Windows Firewall may ask to allow Python to use the network -> **Allow**.
- No extra OS permissions are needed on Windows (unlike macOS).

That's it. On the Mac, open the dashboard, pick this machine, enter the code, and
control it.

## Notes
- `ws://` is fine on a trusted LAN. Over the internet use `wss://` (TLS) — see the
  main README's "Run over the internet" section.
- To avoid passing flags every time, edit the top of `agent.py`:
  ```python
  SERVER_DEFAULT = "ws://MAC_IP:8000"
  SECRET_DEFAULT = "mysecret"
  CODE_DEFAULT   = "123456"
  ```
  then just run `python agent.py`.
