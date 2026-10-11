package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"github.com/maxsupermanhd/wrpl-inspector/v3/wrpl"
	"github.com/maxsupermanhd/wrpl-inspector/v3/wrpl/carve"
	packetecs2 "github.com/maxsupermanhd/wrpl-inspector/v3/wrpl/packet/parser/ecs2"
)

func main() {
	if len(os.Args) == 4 && os.Args[1] == "--carve" { carveDir(os.Args[2], os.Args[3]); return }
	if len(os.Args) < 2 { fmt.Fprintln(os.Stderr, "usage: wtstat_results FILE..."); os.Exit(2) }
	data := map[string]any{}
	for _, path := range os.Args[1:] {
		f, err := os.Open(path)
		if err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(1) }
		r, err := wrpl.OpenReplay(f, true, false, true)
		f.Close()
		if err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(1) }
		if _, ok := data["header"]; !ok {
			data["header"] = map[string]any{
				"session_id": r.Header.SessionHEX(), "start_time": r.Header.StartTime,
				"level": string(r.Header.Raw_Level[:]), "location": string(r.Header.Raw_LocName[:]),
				"version": r.Header.Version,
			}
		}
		if len(r.Results) > 0 {
			v, err := wrpl.ParseBlk(r.Results)
			if err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(1) }
			data["results"] = v
		}
	}
	if err := json.NewEncoder(os.Stdout).Encode(data); err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(1) }
}

func carveDir(dir, hashes string) {
	b, err := os.ReadFile(hashes)
	if err != nil { fail(err) }
	h, err := packetecs2.ReadComponentHashMaps(bytes.NewReader(b))
	if err != nil { fail(err) }
	entries, err := os.ReadDir(dir)
	if err != nil { fail(err) }
	readers := map[int]*wrpl.ReplayReader{}
	files := []*os.File{}
	defer func() { for _, r := range readers { r.Close() }; for _, f := range files { f.Close() } }()
	for _, e := range entries {
		if e.IsDir() || filepath.Ext(e.Name()) != ".wrpl" { continue }
		f, err := os.Open(filepath.Join(dir, e.Name()))
		if err != nil { fail(err) }
		files = append(files, f)
		r, err := wrpl.OpenReplay(f, true, true, true)
		if err != nil { fail(err) }
		readers[int(r.Header.ReplayPartNumber)] = r
	}
	c, err := carve.CarveReplay(readers, *h)
	if err != nil { fail(err) }
	vehicles := map[uint64]map[string]bool{}
	for _, e := range c.Entities {
		if e.PlayerID == 0 || e.ModelName == "" { continue }
		if vehicles[e.PlayerID] == nil { vehicles[e.PlayerID] = map[string]bool{} }
		vehicles[e.PlayerID][e.ModelName] = true
	}
	out := map[string]any{"session_id": fmt.Sprintf("%016x",c.SessionID), "start_time": c.TimeStarted, "level": c.Mission.Level, "players": c.Players, "spawned": vehicles, "errors": c.CarveErrors}
	if err := json.NewEncoder(os.Stdout).Encode(out); err != nil { fail(err) }
}

func fail(err error) { fmt.Fprintln(os.Stderr, err); os.Exit(1) }
