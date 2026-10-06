dev = ENV.fetch("RACK_ENV", "development") == "development"

if dev
  require "rack/unreloader"
  Unreloader = Rack::Unreloader.new(subclasses: %w[Roda]) { Cad::App }
  Unreloader.require File.join(__dir__, "app.rb")
  run Unreloader
else
  require_relative "app"
  run Cad::App.freeze.app
end
