require "rubygems/package"
require "zlib"
require "stringio"
require "fileutils"

module Cad
  # Unpacks an uploaded project (tar or tar.gz) into a work dir, refusing anything that could
  # escape it: absolute paths, "..", links and device files.
  module ProjectArchive
    Invalid = Class.new(StandardError)

    def self.extract(io, dest)
      data = io.read(Config.max_upload_bytes + 1)
      raise Invalid, "archive exceeds #{Config.max_upload_bytes / 1024 / 1024} MB" if data.bytesize > Config.max_upload_bytes

      data = Zlib::GzipReader.new(StringIO.new(data)).read if data.byteslice(0, 2) == "\x1f\x8b".b
      count = 0
      total = 0
      Gem::Package::TarReader.new(StringIO.new(data)) do |tar|
        tar.each do |entry|
          count += 1
          raise Invalid, "archive has more than #{Config.max_files} entries" if count > Config.max_files

          path = safe_path(dest, entry.full_name)
          next unless path

          if entry.directory?
            FileUtils.mkdir_p(path)
          elsif entry.file?
            body = entry.read.to_s
            total += body.bytesize
            raise Invalid, "archive expands beyond #{Config.max_upload_bytes / 1024 / 1024} MB" if total > Config.max_upload_bytes

            FileUtils.mkdir_p(File.dirname(path))
            File.binwrite(path, body)
          else
            raise Invalid, "unsupported entry type in archive: #{entry.full_name}"
          end
        end
      end
      count
    rescue Zlib::Error, Gem::Package::TarInvalidError => e
      raise Invalid, "not a valid tar/tar.gz archive: #{e.message}"
    end

    def self.safe_path(dest, name)
      clean = name.sub(%r{\A\./}, "")
      return nil if clean.empty? || clean == "."
      raise Invalid, "absolute path in archive: #{name}" if clean.start_with?("/")
      raise Invalid, "path escapes archive root: #{name}" if clean.split("/").include?("..")

      File.join(dest, clean)
    end
  end
end
