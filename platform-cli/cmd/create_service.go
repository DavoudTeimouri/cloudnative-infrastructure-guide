// package cmd
//
// Self-service CLI: "cloudnative-guide service create <name>"
// Scaffold a new cloud-native service from the golden path.
// Stdlib-first, no external deps beyond the Go module that owns this file.

package cmd

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/spf13/cobra"
)

// createServiceCmd implements `service create <name>`.
var createServiceCmd = &cobra.Command{
	Use:   "service <name>",
	Short: "Create a new cloud-native service from the golden path",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		ctx := cmd.Context()

		serviceName := args[0]
		ownerTeam, _ := cmd.Flags().GetString("team")
		dataTier, _ := cmd.Flags().GetString("data-tier")
		criticality, _ := cmd.Flags().GetString("criticality")

		opts := goldenPathsCreateOpts{
			serviceName: serviceName,
			ownerTeam:   ownerTeam,
			dataTier:    dataTier,
			criticality: criticality,
		}

		if err := opts.validate(); err != nil {
			return fmt.Errorf("invalid options: %w", err)
		}

		result, err := applyGoldenPath(ctx, opts)
		if err != nil {
			return fmt.Errorf("apply failed (run `platform doctor` to diagnose): %w", err)
		}

		fmt.Printf("✓ Created %s\n", result.serviceName)
		fmt.Printf("  Repo:    %s\n", result.repoURL)
		fmt.Printf("  Cluster: %s\n", result.cluster)
		fmt.Printf("  Time to first deploy: ~%d minutes\n", result.estimatedDeployMinutes)
		return nil
	},
}

func init() {
	createServiceCmd.Flags().String("team", "", "owning team (required)")
	createServiceCmd.Flags().String("data-tier", "none", "data tier: none, postgres, postgres+redis")
	createServiceCmd.Flags().String("criticality", "tier2", "criticality: tier3, tier2, tier1, tier0")
}

type goldenPathsCreateOpts struct {
	serviceName string
	ownerTeam   string
	dataTier    string
	criticality string
}

func (o *goldenPathsCreateOpts) validate() error {
	if o.serviceName == "" {
		return fmt.Errorf("service name is required")
	}
	if o.ownerTeam == "" {
		return fmt.Errorf("--team is required")
	}
	return nil
}

type goldenPathsResult struct {
	serviceName          string
	repoURL              string
	cluster              string
	estimatedDeployMinutes int
}

func applyGoldenPath(ctx context.Context, opts goldenPathsCreateOpts) (*goldenPathsResult, error) {
	// TODO: read golden-path spec, prompt for missing params, emit module dir + deploy.sh
	// For now: scaffold a module under site/modules/<service-name>/
	moduleDir := filepath.Join("site", "modules", opts.serviceName)
	if err := os.MkdirAll(moduleDir, 0755); err != nil {
		return nil, fmt.Errorf("create module dir: %w", err)
	}

	indexHTML := `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Service ` + opts.serviceName + `</title></head>
<body><h1>Service ` + opts.serviceName + `</h1><p>Golden-path scaffolded.</p></body>
</html>`
	if err := os.WriteFile(filepath.Join(moduleDir, "index.html"), []byte(indexHTML), 0644); err != nil {
		return nil, fmt.Errorf("write index.html: %w", err)
	}

	return &goldenPathsResult{
		serviceName:          opts.serviceName,
		repoURL:              "git@github.com:" + strings.ToLower(opts.ownerTeam) + "/" + opts.serviceName + ".git",
		cluster:              "default",
		estimatedDeployMinutes: 12,
	}, nil
}
