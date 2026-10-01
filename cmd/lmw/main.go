// Command lmw is a command-line client for LinkedIn.
package main

import (
	"fmt"
	"os"

	"github.com/MarcZX100/LinkedinMechaWarrior/internal/version"
)

func main() {
	fmt.Fprintf(os.Stderr, "lmw %s: work in progress\n", version.Version)
	os.Exit(1)
}
