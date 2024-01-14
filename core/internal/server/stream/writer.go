package stream

import (
	"context"
	"os"
	"sync"

	"github.com/wandb/wandb/core/internal/observability"
	"github.com/wandb/wandb/core/internal/store"
	pb "github.com/wandb/wandb/core/internal/wandb_core_go_proto"
	"google.golang.org/protobuf/proto"
)

type WriterOption func(*Writer)

func WithWriterFwdChannel(fwd chan *pb.Record) WriterOption {
	return func(w *Writer) {
		w.fwdChan = fwd
	}
}

func WithWriterSettings(settings *pb.Settings) WriterOption {
	return func(w *Writer) {
		w.settings = settings
	}
}

// Writer is responsible for writing messages to the append-only log.
// It receives messages from the handler, processes them,
// if the message is to be persisted it writes them to the log.
// It also sends the messages to the sender.
type Writer struct {
	// ctx is the context for the writer
	ctx context.Context

	// settings is the settings for the writer
	settings *pb.Settings

	// logger is the logger for the writer
	logger *observability.CoreLogger

	// fwdChan is the channel for forwarding messages to the sender
	fwdChan chan *pb.Record

	// storeChan is the channel for messages to be stored
	storeChan chan *pb.Record

	// store is the store for the writer
	store *store.Store

	// recordNum is the running count of stored records
	recordNum int64

	// wg is the wait group for the writer
	wg sync.WaitGroup
}

// NewWriter returns a new Writer
func NewWriter(ctx context.Context, logger *observability.CoreLogger, opts ...WriterOption) *Writer {
	w := &Writer{
		ctx:    ctx,
		logger: logger,
		wg:     sync.WaitGroup{},
	}
	for _, opt := range opts {
		opt(w)
	}
	return w
}

func (w *Writer) startStore() {
	if w.settings.GetXSync().GetValue() {
		// do not set up store if we are syncing an offline run
		return
	}

	w.storeChan = make(chan *pb.Record, BufferSize*8)

	var err error
	w.store = store.New(
		w.ctx,
		store.StoreOptions{
			Name:   w.settings.GetSyncFile().GetValue(),
			Flag:   os.O_WRONLY,
			Header: store.NewHeader(),
		},
	)

	if err = w.store.Open(); err != nil {
		w.logger.CaptureFatalAndPanic("writer: error creating store", err)
	}

	w.wg.Add(1)
	go func() {
		for record := range w.storeChan {
			out, err := proto.Marshal(record)
			if err != nil {
				w.logger.Error("writer: error marshalling record", "error", err)
				continue
			}
			if err = w.store.Write(out); err != nil {
				w.logger.Error("writer: error storing record", "error", err)
			}
		}

		if err = w.store.Close(); err != nil {
			w.logger.CaptureError("writer: error closing store", err)
		}
		w.wg.Done()
	}()
}

// do is the main loop of the writer to process incoming messages
func (w *Writer) Do(inChan <-chan *pb.Record) {
	defer w.logger.Reraise()
	w.logger.Info("writer: started", "stream_id", w.settings.RunId)

	w.startStore()

	for record := range inChan {
		w.handleRecord(record)
	}
	w.Close()
	w.wg.Wait()
}

// Close closes the writer and all its resources
// which includes the store
func (w *Writer) Close() {
	close(w.fwdChan)
	if w.storeChan != nil {
		close(w.storeChan)
	}
	w.logger.Info("writer: closed", "stream_id", w.settings.RunId)
}

// handleRecord Writing messages to the append-only log,
// and passing them to the sender.
// We ensure that the messages are written to the log
// before they are sent to the server.
func (w *Writer) handleRecord(record *pb.Record) {
	w.logger.Debug("write: got a message", "record", record, "stream_id", w.settings.RunId)
	switch record.RecordType.(type) {
	case *pb.Record_Request:
		w.sendRecord(record)
	case nil:
		w.logger.Error("nil record type")
	default:
		w.sendRecord(record)
		w.storeRecord(record)
	}
}

// storeRecord stores the record in the append-only log
func (w *Writer) storeRecord(record *pb.Record) {
	if record.GetControl().GetLocal() {
		return
	}
	w.recordNum += 1
	record.Num = w.recordNum
	w.storeChan <- record
}

func (w *Writer) sendRecord(record *pb.Record) {
	// TODO: redo it so it only uses control
	if w.settings.GetXOffline().GetValue() && !record.GetControl().GetAlwaysSend() {
		return
	}
	w.fwdChan <- record
}
