package postgen

import (
	"strings"
	"testing"
)

func TestGenerateHasHookSectionsAndClosingQuestion(t *testing.T) {
	d, err := Generate("What I learned running a marathon at 40", "casual", "medium")
	if err != nil {
		t.Fatal(err)
	}
	paragraphs := strings.Split(d.Text, "\n\n")
	if paragraphs[0] != "Quick one today: What I learned running a marathon at 40." {
		t.Errorf("hook = %q", paragraphs[0])
	}
	if len(Placeholders(d.Text)) != 2 || !strings.HasSuffix(paragraphs[len(paragraphs)-1], "?") {
		t.Errorf("unexpected draft %q", d.Text)
	}
}

func TestGenerateIsNotTiedToOneTopic(t *testing.T) {
	d, _ := Generate("My first year as an ER nurse", "professional", "long")
	if lower := strings.ToLower(d.Text); strings.Contains(lower, "automat") || strings.Contains(lower, " ai ") {
		t.Errorf("draft is topic-specific: %q", d.Text)
	}
}

func TestGeneratePunctuatesTheIdeaOnce(t *testing.T) {
	cases := map[string]string{
		"Is a marathon at 40 worth it?": "worth it?",
		"We shipped it!":                "shipped it!",
		"Lessons from shipping v2...":   "shipping v2.",
		"Lessons from shipping v2.":     "shipping v2.",
		"  extra   spaces  in   here  ": "extra spaces in here.",
	}
	for idea, end := range cases {
		d, err := Generate(idea, "professional", "short")
		if err != nil {
			t.Fatal(err)
		}
		hook := strings.Split(d.Text, "\n\n")[0]
		if !strings.HasSuffix(hook, end) || strings.Contains(hook, "..") || strings.Contains(hook, "?.") || strings.Contains(hook, "!.") {
			t.Errorf("%q gave hook %q", idea, hook)
		}
	}
}

func TestLengthControlsSections(t *testing.T) {
	for length, want := range map[string]int{"short": 1, "medium": 2, "long": 4} {
		d, _ := Generate("A long enough idea", "technical", length)
		if got := len(Placeholders(d.Text)); got != want {
			t.Errorf("%s: %d sections, want %d", length, got, want)
		}
	}
}

func TestGenerateRejectsInvalidInput(t *testing.T) {
	for _, args := range [][3]string{
		{"A long enough idea", "viral", "medium"},
		{"A long enough idea", "professional", "huge"},
		{"AI", "professional", "medium"},
	} {
		if _, err := Generate(args[0], args[1], args[2]); err == nil {
			t.Errorf("expected an error for %v", args)
		}
	}
}

func TestValidate(t *testing.T) {
	if err := Validate("A finished post. Thoughts?", 3000); err != nil {
		t.Error(err)
	}
	if err := Validate("Arrays start at [0] in Go.", 3000); err != nil {
		t.Error("short brackets are not placeholders")
	}
	draft, _ := Generate("A long enough idea", "professional", "medium")
	for text, want := range map[string]string{
		"   ":                     "empty",
		strings.Repeat("é", 3001): "characters",
		draft.Text:                "placeholder",
	} {
		if err := Validate(text, 3000); err == nil || !strings.Contains(err.Error(), want) {
			t.Errorf("expected %q error, got %v", want, err)
		}
	}
	if err := Validate(strings.Repeat("é", 3000), 3000); err != nil {
		t.Error("the limit counts characters, not bytes")
	}
}

func TestNormalize(t *testing.T) {
	if got := Normalize("\r\n  Hello  \r\nworld\t\n\n"); got != "Hello\nworld" {
		t.Errorf("Normalize = %q", got)
	}
}
