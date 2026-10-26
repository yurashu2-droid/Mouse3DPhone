# 弾を飼う / Bullet Pet prototype

> Implementation: subagent-driven-development; user AGENTS overrides per-task approval/review loops. One integration review and narrow verification. User requested a playable first prototype after choosing the tournament winner.

**Goal:** PC browser battle + iPhone container, capture two-colored enemy shots, tilt to merge matching levels, fire at boss; PC-only demo fallback.
**Architecture:** Python stdlib authoritative game (60Hz), HTTP + SSE snapshots at30Hz. Two Canvas browser pages render at requestAnimationFrame. iOS existing app adds optional WKWebView game mode with native CoreMotion gravity bridge, so LAN HTTP does not rely on Safari motion permissions. Existing Blender behavior remains compatible.
**Tech:** Python3.11+, vanilla JS Canvas, Swift5/iOS16 WebKit/CoreMotion. No npm packages or Unity installation required.
**Spec:** winning concept from 2026-10-26-two-screen-game-tournament.md in original checkout; capture→grow→fire short alternating phases, one boss, two colors. This first prototype deliberately tests tilt + screen, not full6DoF or compressed video.

## Global constraints

- Prototype in `games/bullet_pet/`, no changes to Blender runtime or token.
- Port8767/TCP separate from Blender UDP5005/HTTP5006.
- Single player, 6-digit per-server code; first live client owns input, another gets409; deadman1.5sec pauses game, rejoin requires explicit button.
- Server is authoritative for balls. Client interpolates snapshots, never invents authoritative merges.
- Existing app sends mapped pointer pose, so new game mode obtains raw gravity separately; no camera required for this tilt-only test.
- Scope: one boss, two colors, 120sec round, 5 lives, retry, audio optional after gesture; must work without external assets/network.
- HUD and pages Japanese, keyboard/mouse fallback exposed as PC demo. Motion and PC-only test results distinct from real iPhone verification.

## Shared API contract (implementers must follow)

Static routes: `/` desktop, `/phone?code=123456`, `/assets/desktop.js`, `/assets/phone.js`, `/assets/shared.js`, `/assets/style.css`.

GET `/api/config` (loopback only): `{code, port, urls:["http://LAN:8767/phone?code=..."], version:"0.4.0"}`.
GET `/api/state?code=...`: snapshot below.
GET `/api/events?code=...`: SSE `event: state`, `data: <snapshot>` at30Hz; retry1000.
POST `/api/input`: JSON `{code,client:<uuid>,seq:<increasing integer>,x:<-1..1>,tiltX:<-1..1>,tiltY:<-1..1>,active:true,action:"none"|"join"|"fire",mode:"phone"|"demo"}`. `action:join` explicitly claims/resumes. HTTP200 accepted,409 another client owns,403 wrongcode. `active:false` pauses/releases owner. Values finite/clamped. cap4096bytes.
POST `/api/reset` loopback only: `{code}`; resets state and releases owner. PC sends join again if demo.

Snapshot object:
```
{v:1,tick:0,serverTime:0,phase:"waiting"|"catch"|"grow"|"fire"|"paused"|"won"|"lost",
 phaseLeft:0,timeLeft:120,wave:1,score:0,lives:5,
 boss:{hp:100,maxHp:100,x:0.5},receiver:{x:0.5,width:0.22},aim:0.5,
 balls:[{id:1,x:0.5,y:0.2,vx:0,vy:0,color:"cyan"|"coral",level:1}],
 bullets:[{id:2,x:0.5,y:0.1,color:"cyan"|"coral"}],
 shots:[{id:3,x:0.5,y:0.7,color:"cyan",level:2}],
 fx:[{id:4,type:"capture"|"merge"|"clash"|"hit"|"miss",x:0.5,y:0.5,color:"cyan"}],
 connected:false,controller:null|"phone"|"demo",inputAge:null|0.1}
```
All positions normalized0..1. Desktop bullets fall fromboss towardreceiver y0.86. Container world is square; ball radius `0.038 + level*0.009`; shared export `ballRadius(level)`. Colors cyan/coral. Catch8sec, grow6sec, fire6sec, repeat; manual fire can enter fire fromgrow. Shots travel toward moving boss, hit if aimedx within0.16 when fired. Greaterlevel more damage. Matching color+level collide => merge one level. Opposite colors collide => both removed, one life lost, cooldown0.8sec. Uncaught incoming shots reduce score (not life) to keep prototype playable. No incoming bullets duringgrow/fire. New captures temporarily immune collision0.4sec. Physics uses damped tilt acceleration, wall reflection; no NaN. Output fx retain <=0.65sec.

Phone native bridge:
`window.onNativeMotion({tiltX:<-1..1>,tiltY:<-1..1>,active:true})` at~30Hz afternative start; neutral gravity calibrated at first motion. Browser phone.js uses tiltX also asx, unless manual touchpad override. Page sets `window.bulletPetNative=true` by injected script.
`window.webkit.messageHandlers.bulletPet.postMessage({type:"recenter"})` to recenter; `{type:"ready"}` optional. Native background/dismiss stops CoreMotion and calls active:false. Page visibility hides=>release, neverauto rejoins. Motion is only transmitted after page's explicit Join button, and native packets do not rejoin by themselves.

## Tasks

- [ ] Root: Python core+server, focused stdlib tests for merge/clash/fire/auth/lease/pause, launcher andREADME; authoritative tick and30Hz snapshot.
- [ ] Frontend deliverable: static PC+phone pages, responsive Canvas, connectioncode/IP onPC, mobile pot, tiltpad, fire/recenter/join, phases/results; local PC demo. Own only `games/bullet_pet/web/`.
- [ ] iOS deliverable: GameView.swift WKWebView + native gravity + setuphost/port/code; entry inContentView; Info.plist local networking/motion usage and scoped navigation. Own iOS app sources plus projectgenerator/project. Bump0.4.0/build4. No backend edits.
- [ ] Integration: syntax/tests, actual PC browser flow + second simulated phone + SSE timing, game controls, release/resume, narrow review. CI unsignedIPA build once meaningful set complete; download/verify and localstart server. Phone hardware not available must remain unverified.

## Review focus

- Owner lease: second client cannot silently steer; stale responses/actions cannot reclaim afterreset.
- Background: freeze time and ballphysics; explicit resume required afterreturn.
- SSE reconnect: no duplicate event listeners/loops; stale UI displays connectionlost.
- Native bridge: configured LAN origin only; arbitrarynavigation cannot accessmotion; dismantle stopsmotion.
- UI: phone viewportfits withinnativeview, controls notcropped; PC fallback possible withoutphone. No requestforARcamera inthis tilt-onlymode.

## Ledger

- Initial: isolated manualworktree after native manager reported Not a gitrepository (outer workspace is notgit). Original conceptdocs remain untouched inprimary.
- Ruling: use state+Canvas instead of video streaming or Unity. Fastest test of two screens; price is a 2D gameplay spike rather than a final3D engineSDK.
