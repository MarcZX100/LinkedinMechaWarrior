package config

import (
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

func env(values map[string]string) func(string) string {
	return func(name string) string { return values[name] }
}

func TestFromEnvReadsValues(t *testing.T) {
	dir := t.TempDir()
	cfg, err := FromEnv(env(map[string]string{
		"LMW_STATE_DIR":             dir,
		"LMW_REQUEST_TIMEOUT":       "12",
		"LMW_REQUEST_MIN_DELAY":     "3",
		"LMW_REQUEST_MAX_DELAY":     "9.5",
		"LMW_HOURLY_REQUEST_BUDGET": "20",
		"LMW_DAILY_REQUEST_BUDGET":  "100",
		"LMW_SESSION_STORE":         "File",
	}))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.RequestTimeout != 12*time.Second || cfg.RequestMinDelay != 3*time.Second || cfg.RequestMaxDelay != 9500*time.Millisecond {
		t.Errorf("durations not parsed: %+v", cfg)
	}
	if cfg.HourlyRequestBudget != 20 || cfg.DailyRequestBudget != 100 || cfg.SessionStore != "file" {
		t.Errorf("unexpected config: %+v", cfg)
	}
	if cfg.RequestLogFile() != filepath.Join(dir, "request-log.json") {
		t.Errorf("unexpected request log path %q", cfg.RequestLogFile())
	}
}

func TestDefaultsAreConservative(t *testing.T) {
	cfg, err := FromEnv(env(map[string]string{"LMW_STATE_DIR": t.TempDir()}))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.RequestMinDelay < 2*time.Second || cfg.HourlyRequestBudget > 60 || cfg.SessionStore != "auto" {
		t.Errorf("defaults are not conservative: %+v", cfg)
	}
}

func TestRejectsInvalidAndUnsafeValues(t *testing.T) {
	cases := []map[string]string{
		{"LMW_REQUEST_TIMEOUT": "soon"},
		{"LMW_HOURLY_REQUEST_BUDGET": "many"},
		{"LMW_REQUEST_MIN_DELAY": "0.2"},
		{"LMW_REQUEST_MIN_DELAY": "5", "LMW_REQUEST_MAX_DELAY": "3"},
		{"LMW_HOURLY_REQUEST_BUDGET": "500", "LMW_DAILY_REQUEST_BUDGET": "100"},
		{"LMW_DAILY_REQUEST_BUDGET": "0"},
		{"LMW_MAX_POST_CHARS": "10"},
		{"LMW_SESSION_STORE": "cloud"},
	}
	for _, values := range cases {
		values["LMW_STATE_DIR"] = t.TempDir()
		if _, err := FromEnv(env(values)); err == nil {
			t.Errorf("expected an error for %v", values)
		}
	}
}

func TestDefaultStateDirFollowsPlatformConventions(t *testing.T) {
	base := t.TempDir()
	cfg, err := FromEnv(env(map[string]string{"XDG_STATE_HOME": base, "LOCALAPPDATA": base}))
	if err != nil {
		t.Fatal(err)
	}
	switch runtime.GOOS {
	case "windows":
		if cfg.StateDir != filepath.Join(base, "LinkedinMechaWarrior") {
			t.Errorf("unexpected state dir %q", cfg.StateDir)
		}
	case "darwin":
		if !strings.HasSuffix(cfg.StateDir, filepath.Join("Application Support", "LinkedinMechaWarrior")) {
			t.Errorf("unexpected state dir %q", cfg.StateDir)
		}
	default:
		if cfg.StateDir != filepath.Join(base, "linkedin-mecha-warrior") {
			t.Errorf("unexpected state dir %q", cfg.StateDir)
		}
	}
}
