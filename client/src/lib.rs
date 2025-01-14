use pyo3::prelude::*;

use sentry;
use tracing;
use tracing_subscriber;

pub mod connection;
pub mod launcher;
pub mod printer;
pub mod run;
pub mod session;
pub mod settings;
pub mod wandb_internal;

/// Communication layer between user code and nexus

pub static VERSION: &'static str = env!("CARGO_PKG_VERSION");

#[pyfunction]
pub fn init(settings: Option<settings::Settings>) -> run::Run {
    let actual_settings =
        settings.unwrap_or_else(|| settings::Settings::new(None, None, None, None, None));
    let sess = session::Session::new(actual_settings);
    sess.init_run(None)
}

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
fn wandb(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    // TODO: this doesn't work
    let _guard = sentry::init(
        "https://9e9d0694aa7ccd41aeb5bc34aadd716a@o151352.ingest.sentry.io/4506068829470720",
    );

    let log_level = tracing::Level::INFO;
    // let log_level = tracing::Level::DEBUG;
    tracing_subscriber::fmt().with_max_level(log_level).init();

    m.add("__version__", VERSION)?;
    m.add_function(wrap_pyfunction!(init, m)?)?;
    m.add_class::<settings::Settings>()?;
    m.add_class::<session::Session>()?;
    m.add_class::<run::Run>()?;
    Ok(())
}
