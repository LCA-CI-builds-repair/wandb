package gowandb

import (
	"context"

	"github.com/wandb/wandb/core/internal/gowandb/client/opts/runopts"
	"github.com/wandb/wandb/core/internal/gowandb/client/settings"
	"github.com/wandb/wandb/core/internal/lib/corelib"
	pb "github.com/wandb/wandb/core/internal/wandb_core_go_proto"
)

// Manager is a collection of components that work together to handle incoming
type Manager struct {
	// ctx is the context for the run
	ctx context.Context

	// addr is the address of the server
	addr string

	// settings for all runs
	settings *settings.SettingsWrap
}

// NewManager creates a new manager with the given settings and responders.
func NewManager(ctx context.Context, baseSettings *settings.SettingsWrap, addr string) *Manager {
	manager := &Manager{
		ctx:      ctx,
		settings: baseSettings,
		addr:     addr,
	}
	return manager
}

func (m *Manager) NewRun(runParams *runopts.RunParams) *Run {
	conn := m.Connect(m.ctx)
	// make a copy of the base manager settings
	runSettings := m.settings.Copy()
	if runParams.RunID != nil {
		runSettings.SetRunID(*runParams.RunID)
	} else if runSettings.RunId == nil {
		runSettings.SetRunID(corelib.ShortID(8))
	}
	run := NewRun(m.ctx, runSettings.Settings, conn, runParams)
	return run
}

func (m *Manager) Connect(ctx context.Context) *Connection {
	conn, err := NewConnection(ctx, m.addr)
	// slog.Info("Connecting to server", "conn", conn.Conn.RemoteAddr().String())
	if err != nil {
		panic(err)
	}
	return conn
}

func (m *Manager) Close() {
	conn := m.Connect(m.ctx)
	serverRecord := pb.ServerRequest{
		ServerRequestType: &pb.ServerRequest_InformTeardown{InformTeardown: &pb.ServerInformTeardownRequest{}},
	}
	err := conn.Send(&serverRecord)
	if err != nil {
		return
	}
	conn.Close()
}