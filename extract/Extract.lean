/-
# Extract

Declaration-graph extractor for the NavierStokesAndEuler formalization, adapted from
uda-lab/leray-hopf's `ExtractNotes.lean`.

Imports the already-built oleans for a root module (default
`NavierStokes.ComparatorSolution`), reflects over the environment and writes JSON:

* `decls`: one record per project declaration with `id`, `name`, `kind`, `module`,
  `file`, `startLine`, `endLine`, `signature`, `doc`, `typeDeps` (project declarations
  referenced by the statement), `deps` (referenced by statement or proof) and
  `mathlibDeps` (non-project constants referenced).
* `modules`: one record per project module with its module docstrings and imports.

Unlike `ExtractNotes`, edges through compiler-generated auxiliaries (`_proof_N`,
`match_N`, equation lemmas, …) are followed transitively to the real declarations
behind them instead of being dropped, so proof dependencies hidden in auxiliaries
are kept.

Run from the project root under its search path:

    lake env lean --run Extract.lean -- --root NavierStokes.ComparatorSolution \
      --prefix NavierStokes --out decls.json
-/
import Lean

open Lean Meta

namespace Extract

partial def rootString : Name → String
  | .str .anonymous s => s
  | .str p _          => rootString p
  | .num p _          => rootString p
  | .anonymous        => ""

def moduleToFile (m : Name) : String :=
  "/".intercalate (m.components.map (·.toString)) ++ ".lean"

def moduleOf? (env : Environment) (n : Name) : Option Name :=
  match env.getModuleIdxFor? n with
  | some idx => env.header.moduleNames[idx.toNat]?
  | none     => none

def lastComp : Name → String
  | .str _ s => s
  | _        => ""

def autoLemmaSuffixes : List String :=
  ["injEq", "inj", "sizeOf_spec", "sizeOf_eq", "eq_def", "eq_unfold", "toCtorIdx", "ofNat",
   "noConfusion", "noConfusionType"]

partial def parentIsInductive (env : Environment) : Name → Bool
  | .str p _ =>
      (match env.find? p with | some (.inductInfo _) => true | _ => false)
        || parentIsInductive env p
  | .num p _ => parentIsInductive env p
  | .anonymous => false

/-- Generated or internal constants that are never shown as nodes. -/
def isNoise (env : Environment) (name : Name) (ci : ConstantInfo) : Bool :=
  let userName := (privateToUserName? name).getD name
  (match ci with | .ctorInfo _ | .recInfo _ | .quotInfo _ => true | _ => false)
    || userName.isInternalDetail
    || env.isProjectionFn name
    || isAuxRecursor env name
    || isNoConfusion env name
    || (autoLemmaSuffixes.contains (lastComp name) && parentIsInductive env name)

/-- Owning structure of a projection or constructor. -/
def structuralParent? (env : Environment) (d : Name) : Option Name :=
  let ctorInduct (cn : Name) : Option Name :=
    match env.find? cn with
    | some (.ctorInfo cval) => some cval.induct
    | _                     => none
  if env.isProjectionFn d then
    (env.getProjectionFnInfo? d).bind (fun info => ctorInduct info.ctorName)
  else
    ctorInduct d

def classifyKind (env : Environment) (name : Name) (ci : ConstantInfo) : MetaM String := do
  if isStructure env name then return "structure"
  if (← Meta.isInstance name) then return "instance"
  match ci with
  | .thmInfo _    => return "theorem"
  | .inductInfo _ => return "inductive"
  | .axiomInfo _  => return "axiom"
  | .opaqueInfo _ => return "def"
  | .defnInfo _   => return (if (← isReducible name) then "abbrev" else "def")
  | _             => return "other"

def usedConsts (ci : ConstantInfo) (withValue : Bool) : Array Name :=
  let t := ci.type.getUsedConstants
  if withValue then t ++ ((ci.value? (allowOpaque := true)).map Expr.getUsedConstants).getD #[]
  else t

structure Ctx where
  env    : Environment
  pfx    : String
  kept   : Std.HashSet Name

/-- Resolved dependencies of one constant: project node ids and external constants. -/
structure Deps where
  project  : Std.HashSet Name := {}
  external : Std.HashSet Name := {}
  deriving Inhabited

abbrev AuxCache := Std.HashMap Name Deps

def isProject (c : Ctx) (d : Name) : Bool :=
  match moduleOf? c.env d with
  | some m => rootString m == c.pfx
  | none   => false

/-- Resolve the constants `ds` to node ids, expanding project auxiliaries transitively.
    `visiting` guards against cycles through mutually referencing auxiliaries. -/
partial def resolve (c : Ctx) (ds : Array Name) (visiting : Std.HashSet Name) :
    StateM AuxCache Deps := do
  let mut acc : Deps := {}
  for d in ds do
    if c.kept.contains d then
      acc := { acc with project := acc.project.insert d }
    else if !isProject c d then
      acc := { acc with external := acc.external.insert d }
    else
      match structuralParent? c.env d with
      | some p =>
          if c.kept.contains p then acc := { acc with project := acc.project.insert p }
      | none =>
          if visiting.contains d then continue
          let sub ← match (← get).get? d with
            | some r => pure r
            | none =>
                match c.env.find? d with
                | some ci =>
                    let r ← resolve c (usedConsts ci true) (visiting.insert d)
                    modify (·.insert d r)
                    pure r
                | none => pure {}
          acc := { project := sub.project.fold (·.insert ·) acc.project,
                   external := sub.external.fold (·.insert ·) acc.external }
  return acc

def sortedStrs (s : Std.HashSet Name) (self : Name) : Array Json :=
  ((s.toArray.filter (· != self)).map toString |>.qsort (· < ·)).map Json.str

def truncate (s : String) (n : Nat) : String :=
  if s.length ≤ n then s else (s.take n).toString ++ " …"

def extractAll (rootMod : Name) (pfx : String) : MetaM (Json × String) := do
  let env ← getEnv
  let targets : Array (Name × ConstantInfo) :=
    env.constants.fold (init := #[]) fun acc name ci =>
      match moduleOf? env name with
      | some m => if rootString m == pfx then acc.push (name, ci) else acc
      | none   => acc
  let targets := targets.qsort (fun a b => a.1.toString < b.1.toString)
  let mut kept : Array (Name × ConstantInfo × DeclarationRanges) := #[]
  let mut keptIds : Std.HashSet Name := {}
  for (name, ci) in targets do
    if isNoise env name ci then continue
    let some ranges ← findDeclarationRanges? name | continue
    kept := kept.push (name, ci, ranges)
    keptIds := keptIds.insert name
  let c : Ctx := { env, pfx, kept := keptIds }
  let mut cache : AuxCache := {}
  let mut records : Array Json := #[]
  let mut edges := 0
  for (name, ci, ranges) in kept do
    let (tdeps, cache') := (resolve c (usedConsts ci false) {}).run cache
    let (adeps, cache'') := (resolve c (usedConsts ci true) {}).run cache'
    cache := cache''
    let kind ← classifyKind env name ci
    let sig ← try pure (toString (← Meta.ppExpr ci.type)) catch _ => pure "<pp-error>"
    let doc ← findDocString? env name
    let m := (moduleOf? env name).getD .anonymous
    let deps := sortedStrs adeps.project name
    edges := edges + deps.size
    records := records.push <| Json.mkObj [
      ("id",          Json.str name.toString),
      ("name",        Json.str ((privateToUserName? name).getD name).toString),
      ("private",     Json.bool (privateToUserName? name).isSome),
      ("kind",        Json.str kind),
      ("module",      Json.str m.toString),
      ("file",        Json.str (moduleToFile m)),
      ("startLine",   toJson ranges.range.pos.line),
      ("endLine",     toJson ranges.range.endPos.line),
      ("signature",   Json.str (truncate sig 4000)),
      ("doc",         match doc with | some d => Json.str d | none => Json.null),
      ("typeDeps",    Json.arr (sortedStrs tdeps.project name)),
      ("deps",        Json.arr deps),
      ("mathlibDeps", Json.arr (sortedStrs adeps.external name))
    ]
  let mut mods : Array Json := #[]
  for i in [0:env.header.moduleNames.size] do
    let m := env.header.moduleNames[i]!
    unless rootString m == pfx do continue
    let imports := env.header.moduleData[i]!.imports.map (·.module.toString)
    let docs := (getModuleDoc? env m).getD #[] |>.map (·.doc)
    mods := mods.push <| Json.mkObj [
      ("module",  Json.str m.toString),
      ("file",    Json.str (moduleToFile m)),
      ("imports", Json.arr (imports.map Json.str)),
      ("doc",     Json.arr (docs.map Json.str))
    ]
  let out := Json.mkObj [
    ("root",    Json.str rootMod.toString),
    ("prefix",  Json.str pfx),
    ("decls",   Json.arr records),
    ("modules", Json.arr mods)
  ]
  return (out, s!"kept {records.size} declarations, {edges} edges, {mods.size} modules, \
    {cache.size} auxiliaries expanded")

end Extract

open Extract in
unsafe def main (rawArgs : List String) : IO UInt32 := do
  let args := rawArgs.filter (· != "--")
  let rec parse : List String → Name × String × Option String → Name × String × Option String
    | "--root" :: r :: rest, (_, p, o)   => parse rest (r.toName, p, o)
    | "--prefix" :: p :: rest, (r, _, o) => parse rest (r, p, o)
    | "--out" :: o :: rest, (r, p, _)    => parse rest (r, p, some o)
    | _ :: rest, acc                     => parse rest acc
    | [], acc                            => acc
  let (rootMod, pfx, out?) := parse args (`NavierStokes.ComparatorSolution, "NavierStokes", none)
  Lean.enableInitializersExecution
  Lean.initSearchPath (← Lean.findSysroot)
  let env ← Lean.importModules #[{ module := rootMod }] {} (trustLevel := 1024) (loadExts := true)
  let coreCtx : Core.Context := {
    fileName := "<extract>", fileMap := FileMap.ofString "", maxHeartbeats := 0 }
  let ((json, report), _) ← (extractAll rootMod pfx).run'.toIO coreCtx { env }
  match out? with
  | some path =>
      IO.FS.writeFile path json.compress
      IO.eprintln s!"{report}\nwrote {path}"
  | none => IO.println json.compress
  return 0
